"""
The `bench grade` engine — the benchmark's post-session scoring pass (BENCHMARK.md B2).

Play CAPTURES; grading JUDGES, and it happens here, offline, decoupled from play — no
rate coupling with the model doing the session, and a rubric revision re-grades history
instead of invalidating it (the raw archive is untouched ground truth). This module reads
a batch's condition-stamped archives, pulls out every violation the in-loop checker
flagged, and asks a pinned grader model to score each one — severity, category, a
one-line rationale, and a duplicate marker — via a structured `submit_grade` tool call.
Never by parsing prose: a grade that isn't a tool call is recorded `ungraded`, so an
instrument that isn't doing its job stays visible (the same philosophy as the gate's
`defaulted` flag).

Three pieces:

  * **The grading workspace** — `assemble_grade_ws` lays a *minimal* throwaway project
    under `<out>/grade-ws/`: just the grader agent (`.opencode/agent/grader.md`), the
    bench-only `submit_grade` plugin, and the one npm dep it imports. One Backend boots
    over it for the whole pass. This is instrument, not product — its assets live under
    `gm_llm/bench/assets/`, never the shipped `gm_llm/assets/opencode/`.

  * **Finding extraction** — `findings_from_events` turns an archive into one grading
    unit per flagged verdict (a failed, non-`defaulted` verdict on a turn or a stage
    gate, plus the completeness lint). One brief per finding: focus beats batching. The
    brief carries the rubric verbatim, the turn context, the DRAFT (grade the draft,
    always — the methodology's rule), and the checker's full report.

  * **The grade pass** — `grade_archive` walks a run's findings in order, grades each in
    its own fresh grader session, and writes `grades-<run_id>-<rubric>.jsonl` next to the
    archive: a header line (rubric, grader model/temp, source) then one line per finding.
    Idempotent — a run already graded at this rubric+model is skipped unless `--force`.
    A short window of already-graded findings rides in each brief so the grader can mark a
    violation that persists across consecutive turns `duplicate_of` an earlier one, and
    the persisting violation doesn't multiply the score.

The expensive seams (Backend, the plugin-deps install) are injected so `dev/test_grade.py`
can drive the whole pass — brief construction, the grades-file shape, idempotence, the
ungraded-after-nudge path, dedup, and `--double` agreement — with no network, npm, or
opencode. Stdlib only.
"""

from __future__ import annotations

import json
import re
import shutil
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..orchestrator import Backend, Logs
from ..orchestrator.logs import debug_enabled
from ..project import install_plugin_deps

ASSETS = Path(__file__).resolve().parent / "assets"
RUBRIC = "v1"                # the rubric version this pass grades against
GRADER_AGENT = "grader"
WS_NAME = "grade-ws"         # the grading workspace dir under the batch out-dir

# Sent if the grader ends its turn without submitting a grade — one nudge, then the
# finding is recorded `ungraded` (Backend.ensure_tool drives the retry).
_NUDGE_SUBMIT_GRADE = (
    "You ended your turn without submitting your grade. Call the `submit_grade` tool now "
    "as your only action, with `severity`, `category`, a one-sentence `rationale`, and "
    "`duplicate_of` (a window ref id or an empty string). Output nothing else."
)

# The dedup window handed to the grader: the most recent already-graded findings, and —
# when both carry a turn number — only those within this many turns (a violation ten turns
# apart is not the same persisting one).
_WINDOW_ITEMS = 8
_WINDOW_TURNS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quiet(msg: str) -> None:
    print(f"[bench] {msg}", flush=True)


# ── the grading workspace ────────────────────────────────────────────────────

def _apply_model(agent_md: str, model: str | None) -> str:
    """Override the `model:` line in the grader agent's frontmatter (`--model`, so a
    stronger instrument can re-grade later — grades are derived data). A no-op when
    `model` is None; the asset's own pinned model line stands."""
    if not model:
        return agent_md
    return re.sub(r"(?m)^model:.*$", f"model: {model}", agent_md, count=1)


def assemble_grade_ws(out_dir, *, model: str | None = None, install=install_plugin_deps,
                      note=_quiet) -> Path:
    """Assemble (once) the minimal grading workspace under `<out_dir>/grade-ws/`: the
    grader agent, the `submit_grade` plugin, and the one npm dep it imports. Idempotent —
    a re-invoked grade pass reuses an existing `.opencode/` (never re-pays the install) but
    always re-writes the agent file so a changed `--model` takes effect. Returns the ws dir."""
    ws = Path(out_dir) / WS_NAME
    opencode = ws / ".opencode"
    agent_dir = opencode / "agent"
    plugin_dir = opencode / "plugin"

    fresh = not opencode.is_dir()
    agent_dir.mkdir(parents=True, exist_ok=True)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    grader_md = _apply_model((ASSETS / "grader.md").read_text(encoding="utf-8"), model)
    (agent_dir / f"{GRADER_AGENT}.md").write_text(grader_md, encoding="utf-8")
    shutil.copy2(ASSETS / "submit-grade.ts", plugin_dir / "submit-grade.ts")
    shutil.copy2(ASSETS / "package.json", opencode / "package.json")

    if fresh:
        note(f"preparing grading workspace at {ws} (plugin deps)…")
        ok, msg = install(opencode)
        note(msg if ok else f"WARNING: {msg}")
    else:
        note(f"reusing grading workspace at {ws}")
    return ws


def grader_meta(ws) -> dict:
    """The grader's `{model, temperature}`, parsed from the workspace agent file — the
    same hand-rolled frontmatter read the runner's `agent_conditions` uses (no yaml dep).
    Stamped into every grades-file header so a grade is always traceable to its
    instrument."""
    model, temp = None, 0.0
    try:
        text = (Path(ws) / ".opencode" / "agent" / f"{GRADER_AGENT}.md").read_text(encoding="utf-8")
    except OSError:
        text = ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        block = text[3:end] if end != -1 else ""
        for line in block.splitlines():
            if (m := re.match(r"\s*model:\s*(\S+)", line)):
                model = m.group(1).strip()
            elif (m := re.match(r"\s*temperature:\s*([0-9.]+)", line)):
                temp = float(m.group(1))
    return {"model": model, "temperature": temp}


# ── findings: one grading unit per flagged verdict ───────────────────────────

@dataclass
class Finding:
    """One violation to grade: the checker already flagged it; the grader only scores it.
    `ref` is a stable id (session/turn/stage + check) the dedup window keys off; `draft` is
    the artifact as gated (grade the draft, always); `report` is the checker's prose."""
    ref: str
    kind: str                       # "turn" | "stage"
    check: str                      # check-turn / check-conduct / check-combat / plan / … / lint
    report: str
    player: str = ""                # runtime turns only
    draft: str = ""                 # the as-gated artifact (may be empty for stages the archive doesn't capture)
    session: int | None = None
    turn: int | None = None
    stage: str | None = None


def _flagged(verdict: dict) -> bool:
    """A verdict is a finding when the checker actually flagged it: `passed` is false and it
    is not a `defaulted` pass-by-default (a defaulted verdict is instrument health, counted
    in the report, never graded as a violation)."""
    return verdict.get("passed") is False and not verdict.get("defaulted")


def findings_from_events(events: list[dict]) -> list[Finding]:
    """Every grading unit in one archive's event stream, in play order: one per flagged
    turn verdict (check-turn / check-conduct / check-combat), one per flagged stage gate
    (plan / digest / feedback / propagation / init), and one per completeness-lint miss.
    A turn or stage whose verdicts all passed produces no work."""
    findings: list[Finding] = []
    for e in events:
        ev = e.get("event")
        if ev == "turn":
            session, turn = e.get("session"), e.get("turn")
            player, draft = e.get("player", ""), e.get("draft", "")
            for v in e.get("verdicts", []):
                if _flagged(v):
                    check = v.get("check", "check")
                    findings.append(Finding(
                        ref=f"s{session}t{turn}:{check}", kind="turn", check=check,
                        report=v.get("report", ""), player=player, draft=draft,
                        session=session, turn=turn))
        elif ev == "stage":
            stage = e.get("stage")
            session = e.get("session")
            base = f"s{session}" if session is not None else "init"
            if stage == "lint":
                inc = e.get("incomplete") or 0
                if inc:
                    findings.append(Finding(
                        ref=f"{base}:lint", kind="stage", check="lint",
                        report=(f"{inc} entity file(s) left incomplete after the D1 apply "
                                "pass; the completeness lint flagged them and dispatched one "
                                "correction."),
                        draft="", session=session, stage=stage))
                continue
            v = e.get("verdict")
            if v and _flagged(v):
                findings.append(Finding(
                    ref=f"{base}:{stage}", kind="stage", check=v.get("check", stage),
                    report=v.get("report", ""),
                    draft=e.get("draft") or e.get("plan") or "",
                    session=session, stage=stage))
    return findings


# ── the brief ────────────────────────────────────────────────────────────────

def _where(finding: Finding) -> str:
    if finding.kind == "turn":
        return f"turn {finding.turn} of session {finding.session}"
    if finding.session is not None:
        return f"the {finding.stage} stage gate, session {finding.session}"
    return f"the {finding.stage} stage gate (setup)"


def build_brief(rubric_text: str, finding: Finding, window: list[dict]) -> str:
    """The per-finding grading brief: the rubric verbatim, the flag's context (player
    message, the DRAFT to grade, which check flagged it, the checker's report), and the
    dedup window of already-graded findings. One finding per brief — focus beats
    batching (BENCHMARK.md)."""
    draft_label = ("DRAFT — the narration as flagged, grade THIS" if finding.kind == "turn"
                   else "DRAFT — the record as flagged, grade THIS")
    parts = [
        "# Grade one flagged violation",
        "",
        "The independent checker flagged the violation below during play. Score it per the "
        "rubric — severity and category — and submit with `submit_grade`. Do not re-judge "
        "whether it is a violation, and do not raise new ones.",
        "",
        "## Rubric",
        "",
        rubric_text.strip(),
        "",
        "## The flagged violation",
        "",
        f"- ref: `{finding.ref}`",
        f"- flagged by: `{finding.check}`",
        f"- where: {_where(finding)}",
    ]
    if finding.player:
        parts += ["", "### Player's message this turn", "", finding.player.strip() or "(none)"]
    parts += ["", f"### {draft_label}", "", finding.draft.strip() or "(the draft text was not captured — grade from the checker's report below)"]
    parts += ["", "### The checker's report (why it was flagged)", "", finding.report.strip() or "(no report text)"]
    parts += ["", "## Already-graded findings (for the duplicate check)", ""]
    if window:
        parts += [f"- `{w['ref']}` [{w['severity']}/{w['category']}]: {w['rationale']}" for w in window]
    else:
        parts.append("(none yet — this is the first graded finding of the run.)")
    parts += ["", "## Your task", "",
              "Submit one `submit_grade` call: `severity` and `category` from the rubric, a "
              "one-sentence `rationale`, and `duplicate_of` (a window ref id if this is the "
              "same persisting violation, else an empty string)."]
    return "\n".join(parts)


# ── grading one finding ──────────────────────────────────────────────────────

def _window(finding: Finding, graded: list[dict]) -> list[dict]:
    """The dedup window for `finding`: the most recent already-graded findings, trimmed —
    when both carry a turn — to those within `_WINDOW_TURNS` turns (a distant violation is
    not the same persisting one)."""
    recent = graded[-_WINDOW_ITEMS:]
    if finding.turn is None:
        return recent
    out = []
    for g in recent:
        gt = g.get("turn")
        if gt is None or 0 < finding.turn - gt <= _WINDOW_TURNS:
            out.append(g)
    return out


def grade_finding(backend, finding: Finding, rubric_text: str, window: list[dict],
                  note=_quiet) -> dict:
    """Grade one finding in a fresh grader session. Returns the grade record (severity,
    category, rationale, duplicate_of) or an `ungraded` record if the grader never made a
    usable `submit_grade` call even after one nudge — the instrument's miss is recorded,
    never guessed from prose."""
    base = {"ref": finding.ref, "kind": finding.kind, "check": finding.check,
            "session": finding.session, "turn": finding.turn, "stage": finding.stage}
    sid = backend.create_session("bench-grade")
    reply = backend.prompt_full(sid, GRADER_AGENT, build_brief(rubric_text, finding, window))
    reply = backend.ensure_tool(sid, GRADER_AGENT, reply, tool="submit_grade",
                                nudge=_NUDGE_SUBMIT_GRADE, args=("severity", "category"),
                                tries=1)
    inp = reply.tool_inputs.get("submit_grade") or {}
    severity = str(inp.get("severity", "")).strip()
    category = str(inp.get("category", "")).strip()
    if not (severity and category):
        note(f"  {finding.ref}: no usable grade after nudge — recording ungraded.")
        return {**base, "ungraded": True}
    dup = str(inp.get("duplicate_of", "")).strip()
    return {**base, "severity": severity, "category": category,
            "rationale": str(inp.get("rationale", "")).strip(),
            "duplicate_of": dup or None}


# ── grading one run's archive ────────────────────────────────────────────────

def _read_events(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_id_of(events: list[dict], fallback: str) -> str:
    for e in events:
        if e.get("event") == "run" and e.get("run_id"):
            return e["run_id"]
    return fallback


def _already_graded(grades_path: Path, meta: dict) -> bool:
    """True if `grades_path` already holds a header for this rubric+grader-model — the
    idempotence check (`--force` overrides). A different model or rubric re-grades."""
    try:
        first = _read_events(grades_path)[0]
    except (OSError, ValueError, IndexError):
        return False
    return (first.get("rubric") == RUBRIC
            and (first.get("grader") or {}).get("model") == meta.get("model"))


def grade_archive(backend, archive_path, *, rubric_text: str, meta: dict, force: bool = False,
                  suffix: str = "", limit: int | None = None, note=_quiet) -> Path:
    """Grade one run's archive → `grades-<run_id>-<rubric><suffix>.jsonl` beside it (a
    header line, then one line per finding). Idempotent: an existing file at this
    rubric+model is left untouched unless `force`. `limit` caps how many findings are
    graded (the `--double` sample). Returns the grades path (written or reused)."""
    archive_path = Path(archive_path)
    events = _read_events(archive_path)
    run_id = _run_id_of(events, archive_path.stem.replace("archive-", ""))
    grades_path = archive_path.parent / f"grades-{run_id}-{RUBRIC}{suffix}.jsonl"

    if grades_path.is_file() and not force and _already_graded(grades_path, meta):
        note(f"{grades_path.name}: already graded at {RUBRIC}/{meta.get('model')} — skipping (use --force).")
        return grades_path

    findings = findings_from_events(events)
    if limit is not None:
        findings = findings[:limit]

    header = {"event": "grades", "schema": 1, "rubric": RUBRIC, "grader": meta,
              "graded_at": _now(), "archive": archive_path.name, "run_id": run_id}
    lines = [json.dumps(header, ensure_ascii=False)]
    graded: list[dict] = []
    note(f"grading {len(findings)} finding(s) from {archive_path.name}…")
    for finding in findings:
        grade = grade_finding(backend, finding, rubric_text, _window(finding, graded), note=note)
        lines.append(json.dumps(grade, ensure_ascii=False))
        if not grade.get("ungraded"):
            graded.append({"ref": grade["ref"], "turn": finding.turn,
                           "severity": grade["severity"], "category": grade["category"],
                           "rationale": grade["rationale"]})
    grades_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    note(f"wrote {grades_path.name} ({len(findings)} finding(s)).")
    return grades_path


# ── --double agreement ───────────────────────────────────────────────────────

def _grade_lines(path) -> list[dict]:
    """Just the per-finding grade lines of a grades file (drops the header)."""
    return [e for e in _read_events(path) if e.get("event") != "grades"]


def agreement(path_a, path_b) -> dict:
    """Instrument reliability between two independent grade passes over the same findings:
    exact severity-match and category-match rates over the findings both passes graded
    (ungraded on either side is dropped). `n` is that shared, graded count."""
    a = {g["ref"]: g for g in _grade_lines(path_a) if not g.get("ungraded")}
    b = {g["ref"]: g for g in _grade_lines(path_b) if not g.get("ungraded")}
    shared = sorted(set(a) & set(b))
    if not shared:
        return {"n": 0, "severity_match": None, "category_match": None}
    sev = sum(1 for r in shared if a[r]["severity"] == b[r]["severity"]) / len(shared)
    cat = sum(1 for r in shared if a[r]["category"] == b[r]["category"]) / len(shared)
    return {"n": len(shared), "severity_match": sev, "category_match": cat}


# ── the batch pass ───────────────────────────────────────────────────────────

def _default_backend(directory, *, port, min_gap, turn_timeout, logs, note=_quiet):
    b = Backend(directory, port=port, min_call_gap=min_gap, turn_timeout=turn_timeout, logs=logs)
    b.on_retry = lambda agent, attempt, wait, reason: note(
        f"{agent} call failed: {reason} — retry {attempt} in {wait}s")
    return b


def _batch_archives(out_dir: Path) -> list[Path]:
    """Every run's archive in a batch out-dir, read off `batch.jsonl` (the manifest B1
    writes), resolved to absolute paths. A run recorded with no archive (it died before
    its first emit) is skipped."""
    manifest = out_dir / "batch.jsonl"
    if not manifest.is_file():
        return []
    out = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("archive"):
            out.append(out_dir / rec["archive"])
    return out


def grade_batch(out_dir, *, model: str | None = None, force: bool = False,
                double: bool = False, sample: int | None = None, port: int = 4181,
                min_gap: float = 1.0, turn_timeout: int = 360,
                backend_factory=_default_backend, install=install_plugin_deps,
                note=_quiet) -> dict:
    """Grade every archive in a batch `out_dir`. Assembles the grading workspace once,
    boots one Backend over it, and grades each run to a `grades-*.jsonl` beside its
    archive. `--double` re-grades a sample of each run's findings in fresh sessions
    (suffix `-b`) and reports severity/category agreement. Returns a summary dict
    (graded paths, and the pooled agreement when `double`). Idempotent per run (see
    `grade_archive`)."""
    out_dir = Path(out_dir)
    archives = _batch_archives(out_dir)
    if not archives:
        note(f"no archives found under {out_dir} (need a batch.jsonl with archives).")
        return {"graded": [], "double": None}

    rubric_text = (ASSETS / "rubric-v1.md").read_text(encoding="utf-8")
    ws = assemble_grade_ws(out_dir, model=model, install=install, note=note)
    meta = grader_meta(ws)
    logs = Logs.under(project=ws, debug=debug_enabled())
    backend = backend_factory(ws, port=port, min_gap=min_gap, turn_timeout=turn_timeout,
                              logs=logs, note=note)

    graded_paths: list[Path] = []
    pairs: list[tuple[Path, Path]] = []
    try:
        backend.start()
        for archive in archives:
            note(f"── grading {archive.name} ──")
            primary = grade_archive(backend, archive, rubric_text=rubric_text, meta=meta,
                                    force=force, note=note)
            graded_paths.append(primary)
            if double:
                note(f"── double pass {archive.name} (sample={sample or 'all'}) ──")
                second = grade_archive(backend, archive, rubric_text=rubric_text, meta=meta,
                                       force=True, suffix="-b", limit=sample, note=note)
                pairs.append((primary, second))
    finally:
        note("stopping backend…")
        backend.stop()

    result: dict = {"graded": [str(p) for p in graded_paths], "double": None}
    if double and pairs:
        # Pool shared findings across every run for the batch-level agreement summary.
        sev_hits = cat_hits = n = 0
        for a, b in pairs:
            ag = agreement(a, b)
            if ag["n"]:
                n += ag["n"]
                sev_hits += round(ag["severity_match"] * ag["n"])
                cat_hits += round(ag["category_match"] * ag["n"])
        summary = {"n": n,
                   "severity_match": (sev_hits / n) if n else None,
                   "category_match": (cat_hits / n) if n else None}
        result["double"] = summary
        if n:
            note(f"grader agreement over {n} finding(s): severity {sev_hits/n:.0%}, "
                 f"category {cat_hits/n:.0%}")
        else:
            note("grader agreement: no findings graded in both passes.")
    return result
