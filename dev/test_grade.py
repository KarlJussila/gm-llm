#!/usr/bin/env python3
"""Standalone checks for `bench grade` and `bench report` — no pytest; run me directly.

Writes small archives and checks files directly (the shapes archive.py and check.py write) and
drives the grade and report passes over a fake grader backend with scripted `submit_grade`
replies — no network, no opencode.

Covers: findings in play order from the checks file and the gates, the finding message, one
rolling session with the rubric up front, confirmed / rejected / ungraded, idempotence and the
instrument fingerprint, an unchecked run skipped and flagged, the workspace (start, after,
transcript), dedup, --double agreement, the score model, precision and the defaulted rate in the
report, the t-based interval, thin dimensions, and mixed conditions and grading.
"""

import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.bench import grade, scoring  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    rolls = ()

    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = frozenset(tools)
        self.tool_inputs = tool_inputs or {}


_REF_RE = re.compile(r'<finding ref="([^"]+)"')


class FakeGraderBackend:
    """A grader that reads the finding's ref out of each message and answers from `grades`
    (ref → submit_grade args); a ref not in it gets no tool call, even after the nudge."""

    def __init__(self, grades=None, **kw):
        self.grades = grades or {}
        self.sessions, self.messages = 0, []
        self._last_ref = None

    def start(self):
        return self

    def stop(self):
        pass

    def create_session(self, title=None):
        self.sessions += 1
        return f"sid-{self.sessions}"

    def prompt_full(self, sid, agent, message, whole=False):
        self.messages.append((sid, message))
        if (m := _REF_RE.search(message)):
            self._last_ref = m.group(1)
        if self._last_ref not in self.grades:
            return _Reply("")
        return _Reply("", {"submit_grade"}, {"submit_grade": self.grades[self._last_ref]})

    def ensure_tool(self, sid, agent, reply, *, tool, nudge, args=(), tries=1, whole=False):
        for _ in range(tries):
            inp = reply.tool_inputs.get(tool) or {}
            if tool in reply.tools and all(str(inp.get(a, "")).strip() for a in args):
                break
            reply = self.prompt_full(sid, agent, nudge, whole=whole)
        return reply


def _confirm(severity, category, dup=""):
    return {"verdict": "confirmed", "severity": severity, "category": category,
            "rationale": "holds.", "duplicate_of": dup}


_REJECT = {"verdict": "rejected", "severity": "", "category": "", "rationale": "canon allows it.",
           "duplicate_of": ""}


def _turn(session, turn, *, player="I look around.", narration="The inn is warm.",
          complete=False, context=None):
    return {"event": "turn", "session": session, "turn": turn, "opening": turn == 1,
            "player": player, "narration": narration, "tools": [],
            "session_complete": complete, "context": context}


def _stage(stage, session, *, passed=True, report="", defaulted=False, corrected=False, **kw):
    return {"event": "stage", "stage": stage, "session": session, "corrected": corrected,
            "verdict": {"check": stage, "passed": passed, "defaulted": defaulted, "report": report},
            **kw}


def _finding(ref, claim="Wrong hair colour.", check="canon", category="canon-contradiction",
             continues=None):
    return {"ref": ref, "check": check, "claim": claim, "evidence": "canon says grey",
            "category": category, "continues": continues}


_COND = {"fixture": {"id": "hollowfell-test", "frozen": "2026-07-17", "provisional": True},
         "tier": "low", "turn_cap": 30, "reconcile": True,
         "agents": {"dm-runner": {"model": "openai/gpt-6-luna", "variant": "xhigh"}}}

_META = {"model": "openai/gpt-6.1-sol", "variant": "high"}
_INST = {"sha256": "1111111111111111", "files": 6}
_RUBRIC = (grade.ASSETS / f"rubric-{grade.RUBRIC}.md").read_text(encoding="utf-8")


def _write_run(out_dir, run_id, events, checks=None, conditions=_COND):
    """A run dir with its archive, its checks file (`checks`: turn ref → findings, every turn
    in `events` checked; None leaves the run unchecked) and its manifest line."""
    run_dir = out_dir / f"run-{run_id}"
    logs = run_dir / ".opencode" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    archive = logs / f"archive-{run_id}.jsonl"
    lines = [{"event": "run", "ts": "t", "run_id": run_id, "schema": 1, "gm_llm": "0"}]
    if conditions is not None:
        lines.append({"event": "conditions", "ts": "t", **conditions})
    lines += events
    archive.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    if checks is not None:
        rows = [{"event": "header", "run": run_id}]
        for e in events:
            if e["event"] == "turn":
                ref = f"s{e['session']}t{e['turn']}"
                found = checks.get(ref, [])
                rows.append({"ref": ref, "session": e["session"], "turn": e["turn"],
                             "defaulted": found is None, "findings": found or []})
        grade.checks_path(archive, run_id).write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with (out_dir / "batch.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run": run_id, "run_dir": f"run-{run_id}",
                            "archive": str(archive.relative_to(out_dir)), "outcome": "complete",
                            "turns": sum(1 for e in events if e["event"] == "turn")}) + "\n")
    return archive


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _grade(backend, archive, **kw):
    return grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META,
                               instrument=kw.pop("instrument", _INST), note=lambda m: None, **kw)


# ── findings ──────────────────────────────────────────────────────────────────

def test_findings_in_play_order(tmp):
    events = [_turn(3, 1), _turn(3, 2), _turn(3, 3),
              _stage("lint", 3, verdict=None, incomplete=2),
              _stage("propagation", 3, passed=False, report="1. **Ledger missed.** x\n"
                     "   1. indented, not an item\n2. **State stale.** y", diff="--- a\n+++ b"),
              _stage("digest", 3, passed=True),
              _stage("plan", 4, passed=True, defaulted=True, report="no verdict")]
    checks = [{"session": 3, "turn": 2, "findings": [_finding("s3t2#1"), _finding("s3t2#2")]},
              {"session": 3, "turn": 3, "findings": [_finding("s3t3#1", continues="s3t2#1")]}]
    found = grade.findings_for_run(events, checks)
    assert [f["ref"] for f in found] == ["s3t2#1", "s3t2#2", "s3t3#1", "s3:lint",
                                         "s3:propagation#1", "s3:propagation#2"], found
    prop = found[4]
    assert prop["kind"] == "stage" and prop["correction"] == "--- a\n+++ b", \
        "the correction rides along as a correction, not as the draft the gate judged"
    assert "indented" in prop["report"], "an indented sub-list belongs to its item"
    assert "2 entity file" in found[3]["report"] and found[3]["check"] == "lint"

    turn_msg = grade.finding_message(found[2])
    assert 'ref="s3t3#1"' in turn_msg and 'turn="s3t3"' in turn_msg
    assert "Claim: Wrong hair colour." in turn_msg and "Continues: s3t2#1" in turn_msg
    assert '<turn ref="s3t3">' in turn_msg and "The inn is warm." in turn_msg, "the turn rides along"
    stage_msg = grade.finding_message(prop)
    assert 'from="gate"' in stage_msg and "Ledger missed" in stage_msg
    assert "<correction>" in stage_msg and "<draft>" not in stage_msg


def test_split_report(tmp):
    assert grade.split_report("1. **Only one.** Sole problem.") == ["1. **Only one.** Sole problem."]
    assert grade.split_report("no list at all") == ["no list at all"]
    pre = grade.split_report("Preamble line.\n1. **A.** a\n2. **B.** b")
    assert len(pre) == 2 and pre[0].startswith("Preamble line."), "a preamble rides with item 1"


# ── the grade pass ────────────────────────────────────────────────────────────

def test_one_session_verdicts_and_idempotence(tmp):
    archive = _write_run(tmp, "r1", [_turn(1, 1), _turn(1, 2), _turn(1, 3)],
                         {"s1t1": [_finding("s1t1#1")], "s1t2": [_finding("s1t2#1")],
                          "s1t3": [_finding("s1t3#1")]})
    backend = FakeGraderBackend({"s1t1#1": _confirm("minor", "canon-contradiction"),
                                 "s1t2#1": _REJECT})
    path = _grade(backend, archive)
    assert backend.sessions == 1, "one rolling session per run"
    finding_msgs = [m for _, m in backend.messages if "<finding " in m]
    assert "<rubric>" in finding_msgs[0] and "Severity — by player-facing consequence" in finding_msgs[0]
    assert all("<rubric>" not in m for m in finding_msgs[1:]), "the rubric goes in once"

    header, g1, g2, g3 = _lines(path)
    assert path.name == f"grades-r1-{grade.RUBRIC}.jsonl"
    assert header["event"] == "grades" and header["grader"] == _META and header["instrument"] == _INST
    assert g1["verdict"] == "confirmed" and g1["severity"] == "minor" and g1["duplicate_of"] is None
    assert g2 == {"ref": "s1t2#1", "kind": "turn", "check": "canon", "session": 1, "turn": 2,
                  "stage": None, "verdict": "rejected", "rationale": "canon allows it."}
    assert g3.get("ungraded") is True and "severity" not in g3, "a miss is recorded, never guessed"

    _grade(backend, archive)
    assert backend.sessions == 1, "an already-graded run is skipped"
    _grade(backend, archive, instrument={"sha256": "2222222222222222", "files": 6})
    assert backend.sessions == 2, "a changed instrument re-grades"
    _grade(backend, archive, instrument={"sha256": "2222222222222222", "files": 6}, force=True)
    assert backend.sessions == 3, "--force re-grades"


def test_confirmed_needs_a_severity(tmp):
    archive = _write_run(tmp, "r1", [_turn(1, 1)], {"s1t1": [_finding("s1t1#1")]})
    backend = FakeGraderBackend({"s1t1#1": {**_confirm("", "agency")}})
    assert _lines(_grade(backend, archive))[1].get("ungraded") is True


def test_unchecked_run_is_skipped_and_flagged(tmp):
    archive = _write_run(tmp, "r1", [_turn(1, 1, complete=True)])
    backend = FakeGraderBackend()
    assert _grade(backend, archive) is None and backend.sessions == 0
    text = scoring.format_report(scoring.summarize_batch(tmp))
    assert "UNCHECKED RUNS" in text and "r1" in text


def test_grade_batch_workspace_and_double(tmp):
    out = tmp / "out"
    run = out / "run-x"
    (run / "campaign").mkdir(parents=True)
    (run / "campaign" / "INDEX.md").write_text("before play\n", encoding="utf-8")
    (run / ".gitignore").write_text(".opencode/\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "initial state"]):
        subprocess.run(["git", *args], cwd=run, check=True, capture_output=True)
    (run / "campaign" / "INDEX.md").write_text("after reconcile\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "post-session"], cwd=run, check=True,
                   capture_output=True)
    _write_run(out, "x", [_turn(1, 1, narration="Rain on the shutters.", complete=True)],
               {"s1t1": [_finding("s1t1#1")]})

    result = grade.grade_batch(
        out, double=True, note=lambda m: None,
        backend_factory=lambda ws, **kw: FakeGraderBackend(
            {"s1t1#1": _confirm("minor", "canon-contradiction")}))
    ws = out / "grade-ws" / "run-x"
    assert (ws / "campaign" / "INDEX.md").read_text(encoding="utf-8") == "before play\n"
    assert (ws / "after" / "campaign" / "INDEX.md").read_text(encoding="utf-8") == "after reconcile\n"
    assert "Rain on the shutters." in (ws / "transcript.md").read_text(encoding="utf-8")
    assert (ws / ".opencode" / "agent" / "grader.md").is_file()
    assert len(result["graded"]) == 1
    d = result["double"]
    assert d["n"] == 1 and d["verdict_match"] == 1.0 and d["severity_match"] == 1.0
    assert list((run / ".opencode" / "logs").glob(f"grades-x-{grade.RUBRIC}-b.jsonl"))


def test_agreement(tmp):
    a, b = tmp / "a.jsonl", tmp / "b.jsonl"
    head = {"event": "grades"}
    a.write_text("".join(json.dumps(x) + "\n" for x in [
        head, {"ref": "r1", **_confirm("major", "agency")}, {"ref": "r2", **_confirm("minor", "pacing")},
        {"ref": "r3", **_REJECT}, {"ref": "r4", **_confirm("major", "spoiler-leak")}]), encoding="utf-8")
    b.write_text("".join(json.dumps(x) + "\n" for x in [
        head, {"ref": "r1", **_confirm("major", "agency")}, {"ref": "r2", **_confirm("major", "pacing")},
        {"ref": "r3", **_confirm("minor", "agency")}, {"ref": "r4", "ungraded": True}]), encoding="utf-8")
    ag = grade.agreement(a, b)
    assert ag["n"] == 3, "r4 is ungraded on one side"
    assert abs(ag["verdict_match"] - 2 / 3) < 1e-9
    assert ag["confirmed_both"] == 2 and ag["severity_match"] == 0.5 and ag["category_match"] == 1.0


def test_instrument_fingerprint(tmp):
    assets = tmp / "assets"
    assets.mkdir()
    (assets / "rubric-v2.md").write_text("severity: minor|major\n", encoding="utf-8")
    (assets / "grader.md").write_text("grade it\n", encoding="utf-8")
    before = grade.instrument_fingerprint(assets)
    assert before["files"] == 2 and len(before["sha256"]) == 16
    (assets / "rubric-v2.md").write_text("severity: minor|major|critical\n", encoding="utf-8")
    assert grade.instrument_fingerprint(assets)["sha256"] != before["sha256"]
    (assets / "rubric-v2.md").write_text("severity: minor|major\n", encoding="utf-8")
    assert grade.instrument_fingerprint(assets)["sha256"] == before["sha256"]
    assert grade.instrument_fingerprint(tmp / "missing").get("files") == 0


def test_unmanifested_archive_is_flagged(tmp):
    archive = _write_run(tmp, "ok", [_turn(1, 1, complete=True)], {})
    assert grade.unmanifested_archives(tmp) == []
    stray = archive.parent / "archive-9999.jsonl"
    stray.write_text(json.dumps({"event": "run", "run_id": "9999"}) + "\n", encoding="utf-8")
    assert grade.unmanifested_archives(tmp) == [stray]
    backup = archive.parent / "pre-fold-backup"
    backup.mkdir()
    (backup / "archive-0000.jsonl").write_text("{}\n", encoding="utf-8")
    assert grade.unmanifested_archives(tmp) == [stray], "backup dirs are excluded"
    text = scoring.format_report(scoring.summarize_batch(tmp))
    assert "UNMANIFESTED ARCHIVES" in text and stray.name in text


# ── the report ────────────────────────────────────────────────────────────────

def test_score_model(tmp):
    scored = [{"ref": "a", **_confirm("critical", "spoiler-leak")},
              {"ref": "b", **_confirm("major", "fabrication")},
              {"ref": "c", **_confirm("major", "canon-contradiction")},
              {"ref": "d", **_confirm("minor", "agency")},
              {"ref": "e", **_confirm("major", "fabrication", dup="b")},
              {"ref": "f", **_REJECT},
              {"ref": "g", "ungraded": True}]
    s = scoring.score_violations(scored, 20)
    assert s["penalty"] == 12 + 4 + 4 + 1, "dups, rejections and ungraded cost nothing"
    assert s["rate"] == 21 / 20
    assert abs(s["score"] - 100 * (1 - (21 / 20) / 2)) < 1e-6
    dims = s["dimensions"]
    assert dims["canon_fidelity"]["penalty"] == 8 and dims["canon_fidelity"]["violations"] == 2
    assert dims["information_discipline"]["penalty"] == 12
    assert dims["mechanical_integrity"]["score"] == 100, "a clean dimension scores 100"
    deficit = sum(100 - d["score"] for d in dims.values())
    assert abs(deficit - (100 - s["score"])) < 1e-6, "the deficits decompose additively"
    assert scoring.score_violations([], 0)["score"] is None
    odd = scoring.score_violations([{"ref": "x", **_confirm("catastrophic", "agency")}], 10)
    assert odd["off_rubric_severities"] == 1 and odd["penalty"] == 0


def test_rubric_penalty_table_matches_the_score_model(tmp):
    rows = dict(re.findall(r"(?m)^\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|\s*$", _RUBRIC))
    assert rows, "the rubric's penalty table is gone or no longer parses"
    assert {s: float(p) for s, p in rows.items()} == scoring._PENALTY


def test_report_aggregation(tmp):
    out = tmp / "out"
    out.mkdir()
    a1 = _write_run(out, "run1", [
        _turn(1, 1, context={"tokens": 1000, "limit": 100000}),
        _turn(1, 2), _turn(1, 3, complete=True, context={"tokens": 3000, "limit": 100000}),
        _stage("propagation", 1, passed=False, report="State stale.", corrected=True),
        _stage("digest", 1, passed=True)],
        {"s1t1": [_finding("s1t1#1"), _finding("s1t1#2")], "s1t2": None,
         "s1t3": [_finding("s1t3#1", continues="s1t1#1")]})
    a2 = _write_run(out, "run2", [_turn(1, 1, complete=True)], {})
    backend = FakeGraderBackend({"s1t1#1": _confirm("major", "canon-contradiction"),
                                 "s1t1#2": _REJECT,
                                 "s1t3#1": _confirm("major", "canon-contradiction", dup="s1t1#1"),
                                 "s1:propagation": _confirm("minor", "record-integrity")})
    _grade(backend, a1)
    _grade(backend, a2)

    batch = scoring.summarize_batch(out)
    r1 = next(r for r in batch["runs"] if r["run_id"] == "run1")
    assert r1["checker"] == {"confirmed": 2, "rejected": 1, "precision": 2 / 3}
    assert r1["gates"]["precision"] == 1.0
    assert r1["defaulted"] == 1 and r1["judged"] == 5, "3 checked turns and 2 gate verdicts"
    assert r1["violations_raw"] == 3 and r1["violations_dedup"] == 2
    assert r1["stage_correction_rate"] == 0.5 and r1["context_growth"]["delta"] == 2000
    assert batch["checker"]["precision"] == 2 / 3 and batch["unchecked"] == []
    text = scoring.format_report(batch)
    assert "checker precision      : 67%" in text and "gate precision" in text
    assert "defaulted rate" in text and "stages corrected" in text
    assert "MIXED CONDITIONS" not in text


def test_mixed_grading_instruments_are_flagged(tmp):
    out = tmp / "out"
    out.mkdir()
    a1 = _write_run(out, "run1", [_turn(1, 1, complete=True)], {"s1t1": [_finding("s1t1#1")]})
    a2 = _write_run(out, "run2", [_turn(1, 1, complete=True)], {"s1t1": [_finding("s1t1#1")]})
    b = FakeGraderBackend({"s1t1#1": _confirm("major", "canon-contradiction")})
    _grade(b, a1)
    _grade(b, a2, instrument={"sha256": "2222222222222222", "files": 6})
    batch = scoring.summarize_batch(out)
    assert batch["mixed_grading"] and len(batch["grading"]) == 2
    assert "MIXED GRADING" in scoring.format_report(batch)
    _grade(b, a2, force=True)
    batch = scoring.summarize_batch(out)
    assert not batch["mixed_grading"] and "MIXED GRADING" not in scoring.format_report(batch)


def test_thin_dimensions_are_flagged(tmp):
    out = tmp / "out"
    out.mkdir()
    a = _write_run(out, "runT", [_turn(1, 1, complete=True)], {"s1t1": [_finding("s1t1#1")]})
    _grade(FakeGraderBackend({"s1t1#1": _confirm("major", "dice-and-uncertainty")}), a)
    batch = scoring.summarize_batch(out)
    assert batch["dimension_violations"]["mechanical_integrity"] == 1
    text = scoring.format_report(batch)
    assert f"under {scoring._THIN_DIMENSION} violations" in text and "never as a number to track" in text


def test_mean_ci_uses_t_not_z(tmp):
    vals = [31.25, 32.24, 38.0, 49.64, 63.46]
    ci = scoring.mean_ci95(vals)
    sd = statistics.stdev(vals)
    assert abs(ci - 2.776 * sd / 5 ** 0.5) < 0.01, "t(4)=2.776, not z=1.96"
    assert scoring.mean_ci95(vals * 4) < ci, "more runs, tighter interval"
    assert scoring._t95(4) > scoring._t95(19) > scoring._t95(10_000) == 1.960
    assert scoring.mean_ci95([42.0]) is None and scoring.mean_ci95([]) is None
    assert scoring._t95(35) == scoring._t95(30), "an unlisted df takes the next row down"
    assert scoring.resolution95(vals) > ci and scoring.resolution95([42.0]) is None


def test_mixed_conditions_and_the_turn_cap(tmp):
    out = tmp / "out"
    out.mkdir()
    _write_run(out, "runA", [_turn(1, 1, complete=True)], {})
    _write_run(out, "runB", [_turn(1, 1, complete=True)], {}, conditions={**_COND, "turn_cap": 50})
    batch = scoring.summarize_batch(out)
    assert not batch["mixed_conditions"] and batch["capped_runs"] == [], "an unreached cap is no condition"

    _write_run(out, "runC", [_turn(1, 1), {"event": "cap", "ts": "t", "turns": 1}], {})
    text = scoring.format_report(scoring.summarize_batch(out))
    assert "TURN-CAP TRUNCATED" in text

    other = {**_COND, "agents": {"dm-runner": {"model": "openai/gpt-6.1-sol", "variant": "high"}}}
    _write_run(out, "runD", [_turn(1, 1, complete=True)], {}, conditions=other)
    batch = scoring.summarize_batch(out)
    assert batch["mixed_conditions"] and len(batch["conditions"]) == 2
    assert "DO NOT COMPARE" in scoring.format_report(batch)


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failures = 0
    for test in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"  ✓ {test.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"  ✗ {test.__name__}: {e}")
    print(f"\n{'FAIL' if failures else 'OK'} — {len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    for key, value in {"GIT_AUTHOR_NAME": "test", "GIT_COMMITTER_NAME": "test",
                       "GIT_AUTHOR_EMAIL": "test@example.invalid",
                       "GIT_COMMITTER_EMAIL": "test@example.invalid"}.items():
        os.environ.setdefault(key, value)
    main()
