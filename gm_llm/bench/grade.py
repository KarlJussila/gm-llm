"""
`bench grade` — the grader (design/benchmark.md § Grade).

For each run in a batch, one rolling `grader` session (Sol at `high`) takes the run's findings in
play order — the after-play checker's, from `checks-<run_id>.jsonl`, and the between-session
gates', from the archive — and confirms or rejects each through `submit_grade`. A confirmed
finding gets a severity, a category, a rationale and `duplicate_of`; a rejection is a checker (or
gate) false positive, which is what the report's precision counts. A finding with no usable call
after one nudge is recorded `ungraded`.

The workspace, `<out>/grade-ws/<run>/`, holds the campaign before play (as the checker saw it),
the campaign at the end of the run under `after/`, and the session as `transcript.md`, so the
grader decides each finding with file access rather than on the checker's word.

Output is `grades-<run_id>-<rubric>.jsonl` beside the archive: a header (rubric label,
instrument fingerprint, grader model and variant), then one line per finding. Idempotent per
header unless `force`; `--double` grades a sample again in a second session and reports
agreement. A run that hasn't been checked is skipped — its turns would score as clean.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..orchestrator import Backend, Logs
from ..orchestrator.logs import debug_enabled
from .workspace import agent_meta, apply_model, extract_commit, turn_message

ASSETS = Path(__file__).resolve().parent / "assets"
RUBRIC = "v2"
GRADER_AGENT = "grader"
WS_NAME = "grade-ws"

_NUDGE = ("Call `submit_grade` now for that finding: `verdict` confirmed or rejected, and for a "
          "confirmed one a severity and category.")

# A gate's report enumerates its violations as a top-level numbered list ("1. **Title.** …"),
# each graded separately. Column 0 only: indented numbering belongs to an item's sub-list.
_ITEM_RE = re.compile(r"(?m)^(\d+)\.[ \t]+(?=\S)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quiet(msg: str) -> None:
    print(f"[bench] {msg}", flush=True)


def _read_events(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _run_id_of(events: list[dict], fallback: str) -> str:
    for e in events:
        if e.get("event") == "run" and e.get("run_id"):
            return e["run_id"]
    return fallback


def checks_path(archive, run_id: str) -> Path:
    return Path(archive).with_name(f"checks-{run_id}.jsonl")


def grades_path(archive, run_id: str, suffix: str = "") -> Path:
    return Path(archive).with_name(f"grades-{run_id}-{RUBRIC}{suffix}.jsonl")


def instrument_fingerprint(assets=ASSETS) -> dict:
    """A content hash over every file in the instrument's assets — the checker, the grader, the
    rubric and their tools. The rubric label is hand-typed and doesn't move when the prose under
    it does; the hash does. Never raises: an unreadable tree yields `{"error": ...}`."""
    h, files = hashlib.sha256(), 0
    try:
        for path in sorted(Path(assets).rglob("*"), key=lambda p: p.relative_to(assets).as_posix()):
            if not path.is_file():
                continue
            h.update(f"{path.relative_to(assets).as_posix()}\0".encode())
            h.update(path.read_bytes())
            h.update(b"\0")
            files += 1
    except OSError as e:
        return {"error": str(e)}
    return {"sha256": h.hexdigest()[:16], "files": files}


# ── the workspace ────────────────────────────────────────────────────────────

def assemble_grade_ws(run_dir, ws, events: list[dict], *, model: str | None = None) -> Path:
    """The run's start and end states, its transcript, and the grader's assets in `ws`,
    replacing what was there."""
    ws = Path(ws)
    if ws.exists():
        shutil.rmtree(ws)
    extract_commit(run_dir, ws)
    extract_commit(run_dir, ws / "after", "HEAD")
    turns = [turn_message(e) for e in events if e.get("event") == "turn"]
    (ws / "transcript.md").write_text("\n\n".join(turns) + "\n", encoding="utf-8")
    agent_dir, plugin_dir = ws / ".opencode" / "agent", ws / ".opencode" / "plugin"
    agent_dir.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)
    agent = apply_model((ASSETS / f"{GRADER_AGENT}.md").read_text(encoding="utf-8"), model)
    (agent_dir / f"{GRADER_AGENT}.md").write_text(agent, encoding="utf-8")
    shutil.copy2(ASSETS / "submit-grade.ts", plugin_dir / "submit-grade.ts")
    return ws


# ── findings ─────────────────────────────────────────────────────────────────

def split_report(report: str) -> list[str]:
    """A gate's report → one string per violation it enumerated; the whole report when it
    isn't a numbered list. A preamble rides with the first item."""
    text = (report or "").strip()
    marks = list(_ITEM_RE.finditer(text))
    if len(marks) < 2:
        return [text]
    return [text[(0 if i == 0 else m.start()):
                 (marks[i + 1].start() if i + 1 < len(marks) else len(text))].strip()
            for i, m in enumerate(marks)]


def _flagged(verdict: dict | None) -> bool:
    return bool(verdict) and verdict.get("passed") is False and not verdict.get("defaulted")


def findings_for_run(events: list[dict], checks: list[dict]) -> list[dict]:
    """Every finding in one run, in play order: the checker's per turn, then each flagged gate
    (one per violation its report enumerated) and each lint miss where the archive has them."""
    by_turn = {(c.get("session"), c.get("turn")): c.get("findings") or [] for c in checks}
    out: list[dict] = []
    for e in events:
        if e.get("event") == "turn":
            for f in by_turn.get((e.get("session"), e.get("turn")), []):
                out.append({"ref": f["ref"], "kind": "turn", "check": f.get("check"),
                            "session": e.get("session"), "turn": e.get("turn"),
                            "claim": f.get("claim"), "evidence": f.get("evidence"),
                            "category": f.get("category"), "continues": f.get("continues"),
                            "played": turn_message(e)})
        elif e.get("event") == "stage":
            stage, session = e.get("stage"), e.get("session")
            base = {"kind": "stage", "stage": stage, "session": session}
            where = f"s{session}" if session is not None else "setup"
            if stage == "lint":
                if e.get("incomplete"):
                    out.append({**base, "ref": f"{where}:lint", "check": "lint",
                                "report": f"{e['incomplete']} entity file(s) were incomplete "
                                          "after the apply pass; one correction was sent."})
                continue
            v = e.get("verdict")
            if not _flagged(v):
                continue
            items = split_report(v.get("report", ""))
            for i, text in enumerate(items, 1):
                ref = f"{where}:{stage}" + (f"#{i}" if len(items) > 1 else "")
                out.append({**base, "ref": ref, "check": v.get("check", stage),
                            "report": text, "draft": e.get("draft") or "",
                            "correction": e.get("diff") or ""})
    return out


def finding_message(f: dict) -> str:
    """One finding as the grader reads it."""
    if f["kind"] == "turn":
        lines = [f'<finding ref="{f["ref"]}" from="checker" check="{f.get("check")}" '
                 f'turn="s{f["session"]}t{f["turn"]}">',
                 f"Claim: {f.get('claim')}", f"Evidence: {f.get('evidence')}",
                 f"Category guess: {f.get('category')}"]
        if f.get("continues"):
            lines.append(f"Continues: {f['continues']}")
        if f.get("played"):
            lines.append(f["played"])
    else:
        lines = [f'<finding ref="{f["ref"]}" from="gate" check="{f.get("check")}" '
                 f'stage="{f.get("stage")}" session="{f.get("session")}">',
                 "<report>", f.get("report") or "", "</report>"]
        if f.get("draft"):
            lines += ["<draft>", f["draft"], "</draft>"]
        if f.get("correction"):
            lines += ["<correction>", f["correction"], "</correction>"]
    lines.append("</finding>")
    return "\n".join(lines)


# ── grading ──────────────────────────────────────────────────────────────────

def grade_finding(backend, sid: str, f: dict, message: str, note=_quiet) -> dict:
    """Send one finding into the run's grader session and read back its verdict."""
    base = {k: f.get(k) for k in ("ref", "kind", "check", "session", "turn", "stage")}
    reply = backend.prompt_full(sid, GRADER_AGENT, message)
    reply = backend.ensure_tool(sid, GRADER_AGENT, reply, tool="submit_grade", nudge=_NUDGE,
                                args=("verdict",))
    inp = reply.tool_inputs.get("submit_grade") or {}
    verdict = str(inp.get("verdict", "")).strip().lower()
    severity = str(inp.get("severity", "")).strip().lower()
    category = str(inp.get("category", "")).strip().lower()
    rationale = str(inp.get("rationale", "")).strip()
    if verdict == "rejected":
        return {**base, "verdict": "rejected", "rationale": rationale}
    if verdict == "confirmed" and severity and category:
        return {**base, "verdict": "confirmed", "severity": severity, "category": category,
                "rationale": rationale,
                "duplicate_of": str(inp.get("duplicate_of", "")).strip() or None}
    note(f"  {f['ref']}: no usable grade after the nudge — recording ungraded.")
    return {**base, "ungraded": True}


def _already_graded(path: Path, header: dict) -> bool:
    try:
        first = _read_events(path)[0]
    except (OSError, ValueError, IndexError):
        return False
    return (first.get("rubric") == header["rubric"] and first.get("grader") == header["grader"]
            and (first.get("instrument") or {}).get("sha256") == header["instrument"].get("sha256"))


def grade_archive(backend, archive, *, rubric_text: str, meta: dict, instrument: dict,
                  force: bool = False, suffix: str = "", limit: int | None = None,
                  note=_quiet) -> Path | None:
    """Grade one run's findings in a single grader session → its grades file. None when the
    run hasn't been checked."""
    archive = Path(archive)
    events = _read_events(archive)
    run_id = _run_id_of(events, archive.stem)
    checks = checks_path(archive, run_id)
    if not checks.is_file():
        note(f"  {archive.name}: not checked yet — run `bench check` first; skipping.")
        return None
    out = grades_path(archive, run_id, suffix)
    header = {"event": "grades", "rubric": RUBRIC, "instrument": instrument, "grader": meta,
              "graded_at": _now(), "archive": archive.name, "run_id": run_id}
    if not force and _already_graded(out, header):
        note(f"  {out.name}: already graded with this instrument — skipping (--force redoes it)")
        return out

    findings = findings_for_run(events, [c for c in _read_events(checks)
                                         if c.get("event") != "header"])[:limit]
    lines = [header]
    sid = backend.create_session("bench-grade")
    for i, f in enumerate(findings):
        message = finding_message(f)
        if i == 0:
            message = f"<rubric>\n{rubric_text.strip()}\n</rubric>\n\n{message}"
        lines.append(grade_finding(backend, sid, f, message, note=note))
    out.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
                   encoding="utf-8")
    confirmed = sum(1 for g in lines[1:] if g.get("verdict") == "confirmed")
    note(f"  {out.name}: {len(findings)} finding(s), {confirmed} confirmed")
    return out


def agreement(path_a, path_b) -> dict:
    """How two grade passes over the same findings agree: verdict, and severity and category
    where both confirmed."""
    def lines(p):
        return {g["ref"]: g for g in _read_events(p)[1:] if not g.get("ungraded")}
    a, b = lines(path_a), lines(path_b)
    shared = sorted(set(a) & set(b))
    both = [r for r in shared if a[r].get("verdict") == b[r].get("verdict") == "confirmed"]

    def rate(refs, key):
        return sum(a[r].get(key) == b[r].get(key) for r in refs) / len(refs) if refs else None
    return {"n": len(shared), "verdict_match": rate(shared, "verdict"), "confirmed_both": len(both),
            "severity_match": rate(both, "severity"), "category_match": rate(both, "category")}


# ── the batch ────────────────────────────────────────────────────────────────

def _default_backend(directory, *, port, min_gap, turn_timeout, logs, note=_quiet):
    b = Backend(directory, port=port, min_call_gap=min_gap, turn_timeout=turn_timeout, logs=logs)
    b.on_retry = lambda agent, attempt, wait, reason: note(
        f"{agent} call failed: {reason} — retry {attempt} in {wait}s")
    return b


def _batch_archives(out_dir: Path) -> list[Path]:
    """Every run's archive in a batch, from `batch.jsonl`; a run with none is skipped."""
    manifest = Path(out_dir) / "batch.jsonl"
    if not manifest.is_file():
        return []
    return [Path(out_dir) / rec["archive"]
            for rec in (json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()
                        if line.strip())
            if rec.get("archive")]


def unmanifested_archives(out_dir) -> list[Path]:
    """Archives in a batch's run dirs that `batch.jsonl` doesn't point at. The grader and the
    report read only the manifest, so such an archive would score as play that never happened.
    Backup dirs (`*backup`, `pre-*`) are excluded."""
    out_dir = Path(out_dir)
    known = {p.resolve() for p in _batch_archives(out_dir)}
    return [path for path in sorted(out_dir.glob("run-*/.opencode/logs/**/archive-*.jsonl"))
            if not any(part.endswith("backup") or part.startswith("pre-") for part in path.parts)
            and path.resolve() not in known]


def grade_batch(out_dir, *, model: str | None = None, force: bool = False,
                double: bool = False, sample: int | None = None, port: int = 4181,
                min_gap: float = 1.0, turn_timeout: int = 600,
                backend_factory=_default_backend, note=_quiet) -> dict:
    """Grade every run in a batch, each in its own workspace and backend. Returns the grades
    paths and, with `double`, the agreement pooled across runs."""
    out_dir = Path(out_dir)
    for stray in unmanifested_archives(out_dir):
        note(f"WARNING: {stray.relative_to(out_dir)} is not in batch.jsonl — NOT graded. "
             f"Its violations are missing from the score, not zero.")
    archives = _batch_archives(out_dir)
    if not archives:
        note(f"no archives found under {out_dir} (need a batch.jsonl with archives).")
        return {"graded": [], "double": None}

    rubric_text = (ASSETS / f"rubric-{RUBRIC}.md").read_text(encoding="utf-8")
    instrument = instrument_fingerprint()
    graded, pairs = [], []
    for archive in archives:
        run_dir = archive.parents[2]           # <run>/.opencode/logs/<archive>
        note(f"── grading {run_dir.name} ──")
        ws = assemble_grade_ws(run_dir, out_dir / WS_NAME / run_dir.name, _read_events(archive),
                               model=model)
        backend = backend_factory(ws, port=port, min_gap=min_gap, turn_timeout=turn_timeout,
                                  logs=Logs.under(project=ws, debug=debug_enabled()), note=note)
        kw = dict(rubric_text=rubric_text, meta=agent_meta(ws, GRADER_AGENT),
                  instrument=instrument, note=note)
        try:
            backend.start()
            primary = grade_archive(backend, archive, force=force, **kw)
            if primary:
                graded.append(primary)
                if double:
                    pairs.append((primary, grade_archive(backend, archive, force=True,
                                                         suffix="-b", limit=sample, **kw)))
        finally:
            backend.stop()

    result: dict = {"graded": [str(p) for p in graded], "double": None}
    if pairs:
        result["double"] = _pool([agreement(a, b) for a, b in pairs])
    return result


def _pool(agreements: list[dict]) -> dict:
    """Agreement across runs, weighted by each run's shared findings."""
    n = sum(a["n"] for a in agreements)
    both = sum(a["confirmed_both"] for a in agreements)

    def pooled(key, weight):
        w = sum(a[weight] for a in agreements if a[key] is not None)
        return sum(a[key] * a[weight] for a in agreements if a[key] is not None) / w if w else None
    return {"n": n, "verdict_match": pooled("verdict_match", "n"), "confirmed_both": both,
            "severity_match": pooled("severity_match", "confirmed_both"),
            "category_match": pooled("category_match", "confirmed_both")}
