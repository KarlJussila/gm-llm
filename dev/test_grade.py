#!/usr/bin/env python3
"""Standalone checks for the bench grader + report (B2) — no pytest; run me directly.

Synthesizes small score archives (JSONL written directly, matching archive.py's event
shapes) and drives the grade/report passes over a fake grader Backend with scripted
`submit_grade` tool replies — no network, no npm, no opencode. Mirrors dev/test_bench.py's
style (the same _Reply fake, tempdirs, hand-rolled runner over asserts).

Covers: brief construction (draft + report + rubric + window), finding extraction, the
grades-file shape + idempotence, the ungraded-after-nudge path, dedup via duplicate_of,
--double agreement math, and report aggregation (defaulted rate + the mixed-conditions
warning).
"""

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.bench import grade, scoring  # noqa: E402
from gm_llm.bench.grade import Finding  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = frozenset(tools)
        self.tool_inputs = tool_inputs or {}


_REF_RE = re.compile(r"- ref: `([^`]+)`")


class FakeGraderBackend:
    """A grader that never touches opencode: it reads the finding's ref out of the brief
    and returns the scripted grade for it. `grades[ref]` is a dict of submit_grade args;
    a ref in `ungraded` returns no tool call (even after the nudge). Sessions are counted
    so idempotence can assert no work happened on a skip. Mirrors ensure_tool faithfully
    so the nudge path is exercised."""

    def __init__(self, grades=None, ungraded=(), **kw):
        self.grades = grades or {}
        self.ungraded = set(ungraded)
        self.sessions = 0
        self._last_ref = None
        self.started = self.stopped = 0

    def start(self):
        self.started += 1
        return self

    def stop(self):
        self.stopped += 1

    def create_session(self, title=None):
        self.sessions += 1
        return f"sid-{self.sessions}"

    def prompt_full(self, sid, agent, message, whole=False):
        m = _REF_RE.search(message)
        if m:
            self._last_ref = m.group(1)
        ref = self._last_ref
        if ref in self.ungraded or ref not in self.grades:
            return _Reply("", tools=(), tool_inputs={})
        return _Reply("", tools={"submit_grade"}, tool_inputs={"submit_grade": self.grades[ref]})

    def ensure_tool(self, sid, agent, reply, *, tool, nudge, args=(), tries=1, whole=False):
        def satisfied(r):
            if tool not in r.tools:
                return False
            inp = r.tool_inputs.get(tool) or {}
            return all(str(inp.get(a, "")).strip() for a in args)
        for _ in range(tries):
            if satisfied(reply):
                break
            reply = self.prompt_full(sid, agent, nudge, whole=whole)
        return reply


def _verdict(check, passed, report="", defaulted=False):
    return {"check": check, "passed": passed, "defaulted": defaulted, "report": report}


def _turn(session, turn, verdicts, *, player="I look around.", draft="The inn is warm.",
          corrected=False, complete=False, context=None):
    return {"event": "turn", "session": session, "turn": turn, "opening": turn == 1,
            "player": player, "draft": draft, "final": draft, "corrected": corrected,
            "session_complete": complete, "verdicts": verdicts, "canon_sections": 7,
            "context": context}


_COND = {"fixture": {"id": "hollowfell-test", "frozen": "2026-07-17", "provisional": True},
         "tier": "low", "turn_cap": 30, "reconcile": True,
         "agents": {"dm-runner": {"model": "opencode/mimo-v2.5-free", "temperature": 0.3}}}

_META = {"model": "opencode/mimo-v2.5-free", "temperature": 0.0}
_RUBRIC = (grade.ASSETS / "rubric-v1.md").read_text(encoding="utf-8")


def _write_archive(out_dir, run_id, events, conditions=_COND):
    """A run dir with an archive JSONL under it, plus its batch.jsonl manifest line —
    the layout scoring reads. Returns the archive path."""
    run_dir = out_dir / f"run-{run_id}"
    logs = run_dir / ".opencode" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    archive = logs / f"archive-{run_id}.jsonl"
    lines = [{"event": "run", "ts": "t", "run_id": run_id, "schema": 1, "gm_llm": "0"}]
    if conditions is not None:
        lines.append({"event": "conditions", "ts": "t", **conditions})
    lines += events
    archive.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    with (out_dir / "batch.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run": run_id, "run_dir": f"run-{run_id}",
                            "archive": str(archive.relative_to(out_dir)),
                            "outcome": "complete", "turns": len([e for e in events if e["event"] == "turn"])}) + "\n")
    return archive


def _grade_lines(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]


# ── tests ──────────────────────────────────────────────────────────────────────

def test_brief_carries_draft_report_rubric(tmp):
    finding = Finding(ref="s1t2:check-turn", kind="turn", check="check-turn",
                      report="1. Barkeep's hair is black, canon says grey.",
                      player="I greet the barkeep.", draft="His black hair catches the light.",
                      session=1, turn=2)
    window = [{"ref": "s1t1:check-turn", "severity": "minor", "category": "canon-contradiction",
               "rationale": "same wrong hair colour last turn."}]
    brief = grade.build_brief(_RUBRIC, finding, window)
    assert "His black hair catches the light." in brief, "the DRAFT is in the brief"
    assert "canon says grey" in brief, "the checker's report is in the brief"
    assert "Severity — by player-facing consequence" in brief, "the rubric is embedded verbatim"
    assert "s1t1:check-turn" in brief and "wrong hair colour" in brief, "the dedup window is rendered"
    assert "I greet the barkeep." in brief, "the player message is in the brief"


def test_findings_from_events(tmp):
    events = [
        _turn(1, 1, [_verdict("check-turn", True), _verdict("check-conduct", True)]),   # clean → no finding
        _turn(1, 2, [_verdict("check-turn", False, "wrong hair"),
                     _verdict("check-conduct", True)]),                                  # one finding
        _turn(1, 3, [_verdict("check-turn", True, defaulted=True),                       # defaulted → not a finding
                     _verdict("check-conduct", False, "spoke for the PC")]),             # one finding
        {"event": "stage", "stage": "plan", "session": 2,
         "verdict": _verdict("check-plan", False, "unknown NPC"), "corrected": True,
         "committed": False, "draft": "# Session 2 plan\n", "plan": "# fixed\n"},
        {"event": "stage", "stage": "lint", "session": 2, "incomplete": 2, "corrected": True},
    ]
    findings = grade.findings_from_events(events)
    refs = [f.ref for f in findings]
    assert refs == ["s1t2:check-turn", "s1t3:check-conduct", "s2:plan", "s2:lint"], refs
    plan = next(f for f in findings if f.ref == "s2:plan")
    assert plan.draft == "# Session 2 plan\n", "the plan gate grades the as-gated draft"
    lint = next(f for f in findings if f.ref == "s2:lint")
    assert "2 entity file" in lint.report and lint.check == "lint"


_MULTI = (
    "1. **Fabricated NPC identity — Aldric Voss.** No canon entry.\n"
    "   - **Source:** drafted turn.\n"
    "   - **Fix:** defer the name. Two options:\n"
    "     1. leave him unnamed\n"
    "     2. use the papers' name only\n"
    "2. **Gates bypassed — Investigation DC14 not rolled.** Plan line 44.\n"
    "   - **Fix:** call for the roll.\n"
)


def test_split_report(tmp):
    items = grade.split_report(_MULTI)
    assert len(items) == 2, f"two top-level violations, got {len(items)}: {items}"
    assert items[0].startswith("1. **Fabricated NPC")
    assert "leave him unnamed" in items[0], "an indented sub-list belongs to its item, not a new one"
    assert items[1].startswith("2. **Gates bypassed")
    # a single-violation report stays whole; an unnumbered one degrades gracefully
    assert grade.split_report("1. **Only one.** Sole problem.") == ["1. **Only one.** Sole problem."]
    assert grade.split_report("no list at all") == ["no list at all"]
    # nothing in the report is discarded
    pre = grade.split_report("Preamble line.\n\n" + _MULTI)
    assert len(pre) == 2 and pre[0].startswith("Preamble line."), "preamble rides with item 1"


def test_multiple_violations_in_one_verdict_count_separately(tmp):
    findings = grade.findings_from_events([
        _turn(1, 4, [_verdict("check-turn", False, _MULTI), _verdict("check-conduct", True)]),
    ])
    assert [f.ref for f in findings] == ["s1t4:check-turn#1", "s1t4:check-turn#2"]
    assert [(f.item, f.of) for f in findings] == [(1, 2), (2, 2)]
    assert "Aldric" in findings[0].report and "Aldric" not in findings[1].report, \
        "each finding carries only its own violation's prose"
    assert all(f.draft == "The inn is warm." for f in findings), "both grade the same draft"
    # the brief tells the grader these siblings are distinct by construction
    brief = grade.build_brief(_RUBRIC, findings[0], [])
    assert "one of 2 separate violations" in brief and "are not duplicates" in brief


def test_window_spans_same_turn_but_not_same_verdict(tmp):
    """The two checks gate one draft, so a same-turn sibling must be offerable for dedup —
    while siblings the same check enumerated must not be."""
    graded = [
        {"ref": "s1t4:check-turn#1", "turn": 4, "severity": "major",
         "category": "fabrication", "rationale": "invented Voss."},
        {"ref": "s1t4:check-turn#2", "turn": 4, "severity": "major",
         "category": "dice-and-uncertainty", "rationale": "skipped the DC14."},
        {"ref": "s1t1:check-turn", "turn": 1, "severity": "minor",
         "category": "pacing", "rationale": "way back."},
    ]
    sibling = Finding(ref="s1t4:check-conduct", kind="turn", check="check-conduct",
                      report="same overridden roll", session=1, turn=4)
    refs = [w["ref"] for w in grade._window(sibling, graded)]
    assert "s1t4:check-turn#1" in refs, "a same-turn sibling from the OTHER check is dedup-able"

    own = Finding(ref="s1t4:check-turn#3", kind="turn", check="check-turn",
                  report="a third thing", session=1, turn=4, item=3, of=3)
    refs = [w["ref"] for w in grade._window(own, graded)]
    assert refs == ["s1t1:check-turn"], \
        f"siblings of the same verdict are never offered as duplicates, got {refs}"

    # ...and a violation further back than the window is out of range entirely
    far = Finding(ref="s1t9:check-conduct", kind="turn", check="check-conduct",
                  report="much later", session=1, turn=9)
    assert [w["ref"] for w in grade._window(far, graded)] == [], \
        "turn 9 is past the 3-turn window on every graded finding"
    near = Finding(ref="s1t7:check-conduct", kind="turn", check="check-conduct",
                   report="three turns on", session=1, turn=7)
    assert [w["ref"] for w in grade._window(near, graded)] == ["s1t4:check-turn#1",
                                                              "s1t4:check-turn#2"]


def test_score_model(tmp):
    units = 20
    scored = [
        {"ref": "a", "severity": "critical", "category": "spoiler-leak"},
        {"ref": "b", "severity": "major", "category": "fabrication"},
        {"ref": "c", "severity": "major", "category": "canon-contradiction"},
        {"ref": "d", "severity": "minor", "category": "agency"},
        {"ref": "e", "severity": "major", "category": "fabrication", "duplicate_of": "b"},
        {"ref": "f", "severity": "major", "category": "agency", "ungraded": True},
    ]
    s = scoring.score_violations(scored, units)
    assert s["penalty"] == 12 + 4 + 4 + 1, "dups and ungraded cost nothing"
    assert s["rate"] == 21 / 20
    assert abs(s["score"] - 100 * (1 - (21 / 20) / 2)) < 1e-6

    dims = s["dimensions"]
    assert dims["canon_fidelity"]["penalty"] == 8 and dims["canon_fidelity"]["violations"] == 2
    assert dims["information_discipline"]["penalty"] == 12
    assert dims["player_agency"]["penalty"] == 1
    assert dims["mechanical_integrity"]["penalty"] == 0
    assert dims["mechanical_integrity"]["score"] == 100, "a clean dimension scores 100"

    # the headline is computed from the total, not averaged from the subscores — so the
    # deficits decompose additively while every subscore is above its clamp
    deficit = sum(100 - d["score"] for d in dims.values())
    assert abs(deficit - (100 - s["score"])) < 1e-6

    # a run with nothing to divide by scores None rather than a fake 100
    assert scoring.score_violations([], 0)["score"] is None
    # an off-rubric severity is counted, never silently free
    odd = scoring.score_violations([{"ref": "x", "severity": "catastrophic", "category": "agency"}], 10)
    assert odd["off_rubric_severities"] == 1 and odd["penalty"] == 0


def test_rubric_penalty_table_matches_the_score_model(tmp):
    """The rubric shows the grader what each rung costs, so the same numbers now live in
    prose and in code. `_PENALTY` is the authority; this fails the moment they drift."""
    rows = dict(re.findall(r"(?m)^\|\s*(\w+)\s*\|\s*([\d.]+)\s*\|\s*$", _RUBRIC))
    assert rows, "the rubric's penalty table is gone or no longer parses"
    parsed = {sev: float(pts) for sev, pts in rows.items()}
    assert parsed == scoring._PENALTY, f"rubric says {parsed}, code says {scoring._PENALTY}"


def test_grades_file_shape_and_idempotence(tmp):
    archive = _write_archive(tmp, "20260717T000000Z-aaaa", [
        _turn(1, 1, [_verdict("check-turn", False, "wrong hair"), _verdict("check-conduct", True)],
              complete=True),
    ])
    backend = FakeGraderBackend(grades={
        "s1t1:check-turn": {"severity": "minor", "category": "canon-contradiction",
                            "rationale": "cosmetic slip.", "duplicate_of": ""}})
    path = grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)

    lines = _grade_lines(path)
    assert lines[0]["event"] == "grades", "a header line first"
    assert lines[0]["rubric"] == "v1" and lines[0]["grader"]["model"] == _META["model"]
    assert lines[0]["run_id"] == "20260717T000000Z-aaaa"
    g = lines[1]
    assert g["ref"] == "s1t1:check-turn" and g["severity"] == "minor"
    assert g["category"] == "canon-contradiction" and g["duplicate_of"] is None

    # idempotence: a second pass at the same rubric+model does no work
    before = backend.sessions
    grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)
    assert backend.sessions == before, "an already-graded run is skipped, not re-graded"
    # --force re-grades
    grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META, force=True, note=lambda m: None)
    assert backend.sessions == before + 1, "--force re-grades"


def test_ungraded_after_nudge(tmp):
    archive = _write_archive(tmp, "run-ung", [
        _turn(1, 1, [_verdict("check-turn", False, "wrong hair"), _verdict("check-conduct", True)]),
    ])
    backend = FakeGraderBackend(grades={}, ungraded={"s1t1:check-turn"})
    path = grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)
    g = _grade_lines(path)[1]
    assert g.get("ungraded") is True, "a grader miss (even after nudge) is recorded ungraded, never guessed"
    assert "severity" not in g


def test_dedup_via_duplicate_of(tmp):
    # same violation persists across two consecutive turns; the grader marks the second a dup
    archive = _write_archive(tmp, "run-dup", [
        _turn(1, 1, [_verdict("check-turn", False, "wrong hair"), _verdict("check-conduct", True)]),
        _turn(1, 2, [_verdict("check-turn", False, "wrong hair again"), _verdict("check-conduct", True)]),
    ])
    seen_window = {}

    class WindowSpyBackend(FakeGraderBackend):
        def prompt_full(self, sid, agent, message, whole=False):
            m = _REF_RE.search(message)
            if m:
                # record whether the window mentioned turn-1's finding for turn-2's brief
                seen_window[m.group(1)] = "s1t1:check-turn" in message
            return super().prompt_full(sid, agent, message, whole=whole)

    backend = WindowSpyBackend(grades={
        "s1t1:check-turn": {"severity": "minor", "category": "canon-contradiction",
                            "rationale": "wrong hair.", "duplicate_of": ""},
        "s1t2:check-turn": {"severity": "minor", "category": "canon-contradiction",
                            "rationale": "still wrong hair.", "duplicate_of": "s1t1:check-turn"}})
    path = grade.grade_archive(backend, archive, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)
    assert seen_window.get("s1t2:check-turn") is True, "turn 2's brief carried turn 1's graded finding"

    grades = [g for g in _grade_lines(path) if g.get("event") != "grades"]
    summary = scoring.summarize_run(_read := grade._read_events(archive), grades)
    assert summary["violations_raw"] == 2, "both flags counted raw"
    assert summary["violations_dedup"] == 1, "the persisting violation is deduped away"
    assert summary["by_severity_dedup"]["minor"] == 1


def test_double_agreement(tmp):
    a = tmp / "grades-a.jsonl"
    b = tmp / "grades-b.jsonl"
    header = {"event": "grades", "rubric": "v1", "grader": _META}
    a.write_text("\n".join(json.dumps(x) for x in [
        header,
        {"ref": "r1", "severity": "major", "category": "agency"},
        {"ref": "r2", "severity": "minor", "category": "pacing"},
        {"ref": "r3", "severity": "major", "category": "spoiler-leak", "ungraded": False},
    ]) + "\n", encoding="utf-8")
    b.write_text("\n".join(json.dumps(x) for x in [
        header,
        {"ref": "r1", "severity": "major", "category": "agency"},         # both match
        {"ref": "r2", "severity": "major", "category": "pacing"},         # severity differs, category matches
        {"ref": "r3", "ungraded": True},                                  # dropped (ungraded on b)
    ]) + "\n", encoding="utf-8")
    ag = grade.agreement(a, b)
    assert ag["n"] == 2, "only r1,r2 graded on both sides"
    assert abs(ag["severity_match"] - 0.5) < 1e-9, "1 of 2 severities match"
    assert abs(ag["category_match"] - 1.0) < 1e-9, "both categories match"


def test_report_aggregation(tmp):
    out = tmp / "out"
    out.mkdir()
    # run 1: one major violation, one defaulted verdict, a correction
    a1 = _write_archive(out, "run1", [
        _turn(1, 1, [_verdict("check-turn", False, "wrong hair"), _verdict("check-conduct", True)],
              corrected=True, context={"tokens": 1000, "limit": 100000, "threshold": 80000}),
        _turn(1, 2, [_verdict("check-turn", True, defaulted=True), _verdict("check-conduct", True)],
              complete=True, context={"tokens": 3000, "limit": 100000, "threshold": 80000}),
    ])
    a2 = _write_archive(out, "run2", [
        _turn(1, 1, [_verdict("check-turn", True), _verdict("check-conduct", True)], complete=True),
    ])
    b = FakeGraderBackend(grades={
        "s1t1:check-turn": {"severity": "major", "category": "canon-contradiction",
                            "rationale": "misinforms the player.", "duplicate_of": ""}})
    grade.grade_archive(b, a1, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)
    grade.grade_archive(b, a2, rubric_text=_RUBRIC, meta=_META, note=lambda m: None)

    batch = scoring.summarize_batch(out)
    assert batch["n_runs"] == 2 and not batch["mixed_conditions"]
    assert batch["by_severity_raw"].get("major") == 1
    assert batch["defaulted_total"] == 1, "the one defaulted verdict is surfaced"
    assert batch["defaulted_rate"]["max"] > 0, "defaulted rate reported as a distribution"
    r1 = next(r for r in batch["runs"] if r["run_id"] == "run1")
    assert r1["correction_rate"] == 0.5 and r1["context_growth"]["delta"] == 2000
    text = scoring.format_report(batch)
    assert "Instrument health" in text and "defaulted-verdict rate" in text
    assert "MIXED CONDITIONS" not in text, "single-condition batch is not flagged"


def test_mixed_conditions_warning(tmp):
    out = tmp / "out"
    out.mkdir()
    _write_archive(out, "runA", [_turn(1, 1, [_verdict("check-turn", True)], complete=True)])
    other = {**_COND, "agents": {"dm-runner": {"model": "opencode/other-model", "temperature": 0.3}}}
    _write_archive(out, "runB", [_turn(1, 1, [_verdict("check-turn", True)], complete=True)],
                   conditions=other)
    batch = scoring.summarize_batch(out)
    assert batch["mixed_conditions"] is True, "differing agent models → mixed conditions"
    assert len(batch["conditions"]) == 2
    text = scoring.format_report(batch)
    assert "MIXED CONDITIONS" in text and "DO NOT COMPARE" in text


def test_grade_batch_double(tmp):
    out = tmp / "out"
    out.mkdir()
    _write_archive(out, "runX", [
        _turn(1, 1, [_verdict("check-turn", False, "wrong hair"), _verdict("check-conduct", True)],
              complete=True),
    ])
    grades = {"s1t1:check-turn": {"severity": "minor", "category": "canon-contradiction",
                                  "rationale": "cosmetic.", "duplicate_of": ""}}

    def backend_factory(directory, **kw):
        return FakeGraderBackend(grades=grades)

    result = grade.grade_batch(out, backend_factory=backend_factory,
                               install=lambda d: (True, "noop"), double=True, note=lambda m: None)
    assert (out / "grade-ws" / ".opencode" / "agent" / "grader.md").is_file(), "workspace assembled"
    assert len(result["graded"]) == 1
    assert result["double"]["n"] == 1 and result["double"]["severity_match"] == 1.0
    # the -b double-pass file was written beside the archive
    assert list((out / "run-runX" / ".opencode" / "logs").glob("grades-*-v1-b.jsonl")), "second-pass file written"


def main():
    tests = (test_brief_carries_draft_report_rubric, test_findings_from_events,
             test_split_report, test_multiple_violations_in_one_verdict_count_separately,
             test_window_spans_same_turn_but_not_same_verdict, test_score_model,
             test_rubric_penalty_table_matches_the_score_model,
             test_grades_file_shape_and_idempotence, test_ungraded_after_nudge,
             test_dedup_via_duplicate_of, test_double_agreement, test_report_aggregation,
             test_mixed_conditions_warning, test_grade_batch_double)
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
    main()
