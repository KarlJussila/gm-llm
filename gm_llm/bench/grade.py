"""
The `bench grade` engine — the benchmark's post-session scoring pass (design/benchmark.md B2).

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
    unit per *violation*: a failed, non-`defaulted` verdict on a turn or a stage gate is
    split on the numbered list the checker wrote (`split_report`), so a turn that both
    fabricated an NPC and skipped a mandatory check counts twice. Plus the completeness
    lint. One brief per finding: focus beats batching. The brief carries the rubric
    verbatim, the turn context, the DRAFT (grade the draft, always — the methodology's
    rule), and the checker's prose for that violation.

  * **The grade pass** — `grade_archive` walks a run's findings in order, grades each in
    its own fresh grader session, and writes `grades-<run_id>-<rubric>.jsonl` next to the
    archive: a header line (rubric label, instrument fingerprint, grader model/temp, source)
    then one line per finding. Idempotent — a run already graded at this rubric, model and
    instrument hash is skipped unless `--force`.
    A short window of already-graded findings rides in each brief so the grader can mark a
    violation that persists across consecutive turns `duplicate_of` an earlier one, and
    the persisting violation doesn't multiply the score.

The expensive seam (Backend) is injected so `dev/test_grade.py` can drive the whole pass —
brief construction, the grades-file shape, idempotence, the ungraded-after-nudge path,
dedup, and `--double` agreement — with no network or opencode. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..orchestrator import Backend, Logs
from ..orchestrator.logs import debug_enabled

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
# apart is not the same persisting one). Same-turn siblings ARE in the window: two checks
# firing on one draft is the commonest double-count there is.
_WINDOW_ITEMS = 12
_WINDOW_TURNS = 3

# A checker's report enumerates its violations as a top-level markdown list ("1. **Title.**
# …"). Each item is one violation and grades separately — a turn where the runner both
# fabricated an NPC and skipped a mandatory check is two violations, not one. Column-0 only:
# indented numbering belongs to a Fix's sub-list, not to a new finding.
_ITEM_RE = re.compile(r"(?m)^(\d+)\.[ \t]+(?=\S)")


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


def assemble_grade_ws(out_dir, *, model: str | None = None, note=_quiet) -> Path:
    """Assemble the minimal grading workspace under `<out_dir>/grade-ws/`: the grader agent
    and the `submit_grade` plugin. Re-written on every pass, so a changed `--model` takes
    effect. Returns the ws dir."""
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
    note(f"{'prepared' if fresh else 'refreshed'} grading workspace at {ws}")
    return ws


def instrument_fingerprint(assets=ASSETS) -> dict:
    """A content hash over the grading instrument — the rubric, the grader's standing brief,
    and the `submit_grade` tool the grade has to fit through.

    The rubric *version* is a hand-typed label, and a label does not move when the prose
    under it does. `rubric-v1.md` has already been rewritten in place — the penalty table,
    the binding category annotations, the widened dedup window — and every grades file on
    both sides of that edit still says `v1`, so nothing downstream could tell the two apart.
    A grade is only comparable to a grade taken with the same instrument, so the instrument
    is fingerprinted for exactly the reason the prompts are (`runner.prompt_fingerprint`):
    the label records which rubric was *meant*, the hash records which one actually ran.

    Every file under `assets/` counts — the rubric is the criteria, `grader.md` is the
    standing brief, and `submit-grade.ts` is the schema a grade must fit. Hashing the assets rather than the assembled
    workspace is deliberate: `assemble_grade_ws` rewrites all of them from here on every
    pass, so the two agree by construction, and the one thing that legitimately differs —
    a `--model` override — is already recorded separately in the header's `grader` block.

    Relative name and content both feed the digest, walked in sorted order so the hash is
    stable across filesystems. Best-effort like its sibling: an unreadable tree yields
    `{"error": ...}` rather than raising into a grading pass."""
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
    `ref` is a stable id (session/turn/stage + check, suffixed `#n` when the check's report
    enumerated several violations) the dedup window keys off; `draft` is the artifact as
    gated (grade the draft, always); `report` is the checker's prose for this one item."""
    ref: str
    kind: str                       # "turn" | "stage"
    check: str                      # check-turn / check-conduct / check-combat / plan / … / lint
    report: str
    player: str = ""                # runtime turns only
    draft: str = ""                 # the as-gated artifact (may be empty for stages the archive doesn't capture)
    session: int | None = None
    turn: int | None = None
    stage: str | None = None
    item: int = 1                   # 1-based index within the check's report
    of: int = 1                     # how many violations that report enumerated


def split_report(report: str) -> list[str]:
    """A checker's report → one string per violation it enumerated. Checkers write a
    top-level numbered list, one entry per distinct problem (each with its own Source and
    Fix); grading the report as a single unit under-counts a turn that went wrong in two
    unrelated ways. Falls back to the whole report when there is no list to split on (a
    single-violation report, or a checker that didn't number), so an unexpected format
    degrades to the old behaviour instead of dropping content. Any preamble before the
    first item rides with it — nothing in the report is discarded."""
    text = (report or "").strip()
    marks = list(_ITEM_RE.finditer(text))
    if len(marks) < 2:
        return [text]
    items = []
    for i, m in enumerate(marks):
        start = 0 if i == 0 else m.start()       # preamble rides with item 1
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        items.append(text[start:end].strip())
    return items


def _flagged(verdict: dict) -> bool:
    """A verdict is a finding when the checker actually flagged it: `passed` is false and it
    is not a `defaulted` pass-by-default (a defaulted verdict is instrument health, counted
    in the report, never graded as a violation)."""
    return verdict.get("passed") is False and not verdict.get("defaulted")


def _explode(base_ref: str, report: str, **kw) -> list[Finding]:
    """One Finding per violation enumerated in `report`, refs suffixed `#n` when there is
    more than one. A single-violation report keeps the bare ref (and the `-v1` grades of a
    run graded before the split stay ref-comparable)."""
    items = split_report(report)
    n = len(items)
    return [Finding(ref=(f"{base_ref}#{i}" if n > 1 else base_ref), report=text,
                    item=i, of=n, **kw)
            for i, text in enumerate(items, 1)]


def findings_from_events(events: list[dict]) -> list[Finding]:
    """Every grading unit in one archive's event stream, in play order: one per violation
    enumerated by a flagged turn verdict (check-turn / check-conduct / check-combat) or a
    flagged stage gate (plan / digest / feedback / propagation / init), plus one per
    completeness-lint miss. A turn or stage whose verdicts all passed produces no work."""
    findings: list[Finding] = []
    for e in events:
        ev = e.get("event")
        if ev == "turn":
            session, turn = e.get("session"), e.get("turn")
            player, draft = e.get("player", ""), e.get("draft", "")
            for v in e.get("verdicts", []):
                if _flagged(v):
                    check = v.get("check", "check")
                    findings += _explode(
                        f"s{session}t{turn}:{check}", v.get("report", ""),
                        kind="turn", check=check, player=player, draft=draft,
                        session=session, turn=turn)
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
                findings += _explode(
                    f"{base}:{stage}", v.get("report", ""),
                    kind="stage", check=v.get("check", stage),
                    draft=e.get("draft") or e.get("plan") or "",
                    session=session, stage=stage)
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
    batching (design/benchmark.md)."""
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
    if finding.of > 1:
        parts.append(f"- one of {finding.of} separate violations `{finding.check}` raised here; "
                     f"this is #{finding.item}. Grade only this one — the others are graded "
                     f"on their own and are not duplicates of it.")
    if finding.player:
        parts += ["", "### Player's message this turn", "", finding.player.strip() or "(none)"]
    parts += ["", f"### {draft_label}", "", finding.draft.strip() or "(the draft text was not captured — grade from the checker's report below)"]
    label = ("### The checker's finding (why it was flagged)" if finding.of > 1
             else "### The checker's report (why it was flagged)")
    parts += ["", label, "", finding.report.strip() or "(no report text)"]
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

def _verdict_ref(ref: str) -> str:
    """The `s3t7:check-conduct` part of a possibly `#n`-suffixed finding ref."""
    return ref.split("#", 1)[0]


def _window(finding: Finding, graded: list[dict]) -> list[dict]:
    """The dedup window for `finding`: the most recent already-graded findings, trimmed —
    when both carry a turn — to those from the same turn or within `_WINDOW_TURNS` before
    it (a distant violation is not the same persisting one).

    Same-turn siblings are deliberately IN: `check-turn` and `check-conduct` gate the same
    draft, and each flagging the one overriden roll is one violation, not two — the window
    is the only place that can be caught. Siblings from the *same* verdict are just as
    deliberately OUT: the checker already enumerated those as distinct problems, so
    offering them for dedup only invites the grader to collapse a genuine second finding."""
    out = []
    mine = _verdict_ref(finding.ref)
    for g in graded[-_WINDOW_ITEMS:]:
        if _verdict_ref(g["ref"]) == mine:
            continue
        gt = g.get("turn")
        if finding.turn is not None and gt is not None and not (0 <= finding.turn - gt <= _WINDOW_TURNS):
            continue
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


def _already_graded(grades_path: Path, meta: dict, instrument: dict) -> bool:
    """True if `grades_path` already holds a header for this rubric label, grader model *and*
    instrument hash — the idempotence check (`--force` overrides).

    The hash is what gives this teeth. An in-place rubric rewrite keeps the `v1` label, so
    without it a re-grade after sharpening the criteria silently skips every run and leaves
    the batch scored by the old instrument under the new one's name.

    A header written before the fingerprint existed carries no `instrument` and is
    grandfathered — the same call `scoring._condition_signature` makes for pre-fingerprint
    archives. Re-grading a whole banked batch is a worse answer than leaving history
    readable; `--force` is there when a re-grade is what you actually want."""
    try:
        first = _read_events(grades_path)[0]
    except (OSError, ValueError, IndexError):
        return False
    if first.get("rubric") != RUBRIC:
        return False
    if (first.get("grader") or {}).get("model") != meta.get("model"):
        return False
    prior = first.get("instrument")
    return prior is None or prior.get("sha256") == instrument.get("sha256")


def grade_archive(backend, archive_path, *, rubric_text: str, meta: dict, force: bool = False,
                  suffix: str = "", limit: int | None = None, instrument: dict | None = None,
                  note=_quiet) -> Path:
    """Grade one run's archive → `grades-<run_id>-<rubric><suffix>.jsonl` beside it (a
    header line, then one line per finding). Idempotent: an existing file at this
    rubric+model+instrument is left untouched unless `force`. `limit` caps how many findings
    are graded (the `--double` sample). `instrument` is the fingerprint stamped into the
    header, computed here when the caller didn't (a batch computes it once).
    Returns the grades path (written or reused)."""
    archive_path = Path(archive_path)
    instrument = instrument_fingerprint() if instrument is None else instrument
    events = _read_events(archive_path)
    run_id = _run_id_of(events, archive_path.stem.replace("archive-", ""))
    grades_path = archive_path.parent / f"grades-{run_id}-{RUBRIC}{suffix}.jsonl"

    if grades_path.is_file() and not force and _already_graded(grades_path, meta, instrument):
        note(f"{grades_path.name}: already graded at {RUBRIC}/{meta.get('model')} — skipping (use --force).")
        return grades_path

    findings = findings_from_events(events)
    if limit is not None:
        findings = findings[:limit]

    header = {"event": "grades", "schema": 1, "rubric": RUBRIC, "instrument": instrument,
              "grader": meta, "graded_at": _now(), "archive": archive_path.name,
              "run_id": run_id}
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


def unmanifested_archives(out_dir) -> list[Path]:
    """Archives sitting in a batch's run dirs that `batch.jsonl` doesn't point at.

    The grader and the report read the manifest and nothing else, so an archive that isn't
    on it contributes no violations — it scores as a clean stretch of play rather than as
    missing data. That is the worst failure mode an instrument can have, and it is exactly
    what the split-archive incident did (reconcile run as its own `bench run` wrote a second
    stream whose stage findings would have been dropped without a word). Cheap to detect,
    so detect it every time and say so. Backup dirs are excluded — `pre-fold-backup/` and
    friends hold deliberately retired copies."""
    out_dir = Path(out_dir)
    known = {p.resolve() for p in _batch_archives(out_dir)}
    stray = []
    for path in sorted(out_dir.glob("run-*/.opencode/logs/**/archive-*.jsonl")):
        if any(part.endswith("backup") or part.startswith("pre-") for part in path.parts):
            continue
        if path.resolve() not in known:
            stray.append(path)
    return stray


def grade_batch(out_dir, *, model: str | None = None, force: bool = False,
                double: bool = False, sample: int | None = None, port: int = 4181,
                min_gap: float = 1.0, turn_timeout: int = 360,
                backend_factory=_default_backend,
                note=_quiet) -> dict:
    """Grade every archive in a batch `out_dir`. Assembles the grading workspace once,
    boots one Backend over it, and grades each run to a `grades-*.jsonl` beside its
    archive. `--double` re-grades a sample of each run's findings in fresh sessions
    (suffix `-b`) and reports severity/category agreement. Returns a summary dict
    (graded paths, and the pooled agreement when `double`). Idempotent per run (see
    `grade_archive`)."""
    out_dir = Path(out_dir)
    archives = _batch_archives(out_dir)
    for stray in unmanifested_archives(out_dir):
        note(f"WARNING: {stray.relative_to(out_dir)} is not in batch.jsonl — NOT graded. "
             f"Its violations are missing from the score, not zero.")
    if not archives:
        note(f"no archives found under {out_dir} (need a batch.jsonl with archives).")
        return {"graded": [], "double": None}

    rubric_text = (ASSETS / "rubric-v1.md").read_text(encoding="utf-8")
    instrument = instrument_fingerprint()
    note(f"instrument: rubric {RUBRIC} · {instrument.get('sha256', instrument.get('error'))} "
         f"({instrument.get('files', 0)} file(s))")
    ws = assemble_grade_ws(out_dir, model=model, note=note)
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
                                    force=force, instrument=instrument, note=note)
            graded_paths.append(primary)
            if double:
                note(f"── double pass {archive.name} (sample={sample or 'all'}) ──")
                second = grade_archive(backend, archive, rubric_text=rubric_text, meta=meta,
                                       force=True, suffix="-b", limit=sample,
                                       instrument=instrument, note=note)
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
