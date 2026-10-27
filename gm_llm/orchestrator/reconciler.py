"""
POST-session reconcile — the staged pipeline (design/luna.md § Wrap: reconcile).

After a session, canon must absorb what was played. The orchestrator dispatches each step
as its own brief, gates the ones that warrant it in code, and applies at most ONE bounded
correction per gate.

  reconcile_session(N):
    digest      log-extractor: transcript + notes -> digest     gate: check_digest
    feedback    dm: the digest's player feedback -> player store (skipped when there is none)
    canon       dm: new and changed entities, the PC, documents canon lint
    arcs        dm: every arc, each through the `helper` subagent, then the close-out;
                code checks every arc is stamped `as-of: S<N>`, one nudge for any missed
    state       dm: reveals into the ledger, snapshots, current/calendar/clocks
    propagation gate: check_propagation (the whole apply)
    commit "post-session N updates"
    prep        dm (same thread): plan session N+1               gate: check_plan (Planner)

The dm thread runs from feedback through prep, so the apply's warm context carries into
planning. Each stage writes a marker under `.orchestrator/` so a failed run resumes at the
stage it died on instead of re-running the non-idempotent apply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gm_llm.settings import feedback_snapshot, load_settings, project_feedback, push_feedback

from . import paths
from .archive import verdict_fields
from .backend import HEAVY_RETRIES, HEAVY_STALL_TIMEOUT
from .canon import dm_guidance
from .lint import arcs_not_stamped
from .logs import append, banner, section
from .phase import apply_lint_correction, commit_campaign, correct_once
from .planner import Planner, PrepResult  # noqa: F401 — PrepResult used in annotations
from .prompts import load


@dataclass
class ReconcileResult:
    n: int
    digest: "StageGateResult | None" = None       # noqa: F821 — annotation only
    propagation: "StageGateResult | None" = None  # noqa: F821
    lint_incomplete: int = 0      # issues the canon lint found (one correction dispatched)
    arcs_missed: tuple[str, ...] = ()  # arcs left unstamped by the arc pass (one nudge sent)
    prep: "PrepResult | None" = None
    committed: bool = False


class Reconciler:
    """Drives the staged post-session apply, gated stage-by-stage in code."""

    def __init__(self, backend, gate, dm_agent: str = "dm", extractor_agent: str = "log-extractor",
                 on_reconcile=None, on_stage=None, logs=None):
        self.backend = backend
        self.gate = gate
        self.dm_agent = dm_agent
        self.extractor_agent = extractor_agent
        self.on_reconcile = on_reconcile
        self.on_stage = on_stage          # called with a stage key as each stage starts
        self.logs = logs
        self.root = Path(backend.directory)
        # One thread for the dm (feedback through prep), one for the extractor. Checker
        # sessions are spawned per call by the Gate.
        self.dm_sid = backend.create_session("dm apply")
        backend.preface(self.dm_sid, dm_guidance(self.root))
        self.extractor_sid = backend.create_session("log-extractor")

    # -- stage markers (resume-after-failure) -------------------------------

    def _marker_dir(self) -> Path:
        return _marker_dir(self.root)

    def _marker(self, n: int, stage: str) -> Path:
        return _marker_dir(self.root) / f"reconcile-{n}-{stage}.done"

    def _done(self, n: int, stage: str) -> bool:
        return self._marker(n, stage).is_file()

    def _mark(self, n: int, stage: str) -> None:
        try:
            self._marker_dir().mkdir(parents=True, exist_ok=True)
            self._marker(n, stage).write_text(
                datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
        except OSError:
            pass

    def clear_markers(self, n: int) -> None:
        """Wipe session N's stage markers so the next run starts fresh."""
        try:
            for f in self._marker_dir().glob(f"reconcile-{n}-*.done"):
                f.unlink()
        except OSError:
            pass

    def _announce(self, key: str) -> None:
        """Tell a watcher (e.g. the TUI ticker) which stage is starting."""
        if self.on_stage:
            try:
                self.on_stage(key)
            except Exception:
                pass

    # -- the pipeline -------------------------------------------------------

    def reconcile_session(self, n: int, commit: bool = False, prep: bool = True,
                          fresh: bool = False) -> ReconcileResult:
        # The whole pass is heavy calls (whole-transcript extraction, then apply) — widen
        # the stall budget so a slow first token on a large input isn't aborted as a false
        # hang; the ~30-min `turn_timeout` stays the hard backstop. Fewer retries too: a
        # throttled call is a silent hang, so extra attempts just burn budget (a resume
        # restarts the pipeline at the last unfinished stage when caps clear).
        with self.backend.patient(HEAVY_STALL_TIMEOUT, retries=HEAVY_RETRIES):
            return self._reconcile_session(n, commit=commit, prep=prep, fresh=fresh)

    def _reconcile_session(self, n: int, commit: bool = False, prep: bool = True,
                           fresh: bool = False) -> ReconcileResult:
        if fresh:
            self.clear_markers(n)
        rr = ReconcileResult(n)

        # Digest: transcript + notes -> sessions/N/digest.md, gated for source fidelity.
        if not self._done(n, "digest"):
            self._announce("digest")
            self.backend.prompt(self.extractor_sid, self.extractor_agent,
                                load("digest-brief").format(n=n))
            rr.digest = self.gate.check_digest(n)
            draft = self._read_campaign(paths.rel(n, "digest"))
            diff = correct_once(self.backend, self.extractor_sid, self.extractor_agent,
                                rr.digest, self.root)
            self._archive_stage("digest", n, rr.digest, diff, draft=draft)
            self._mark(n, "digest")

        # Feedback: the player's words into the feedback files. Nothing to do — no call —
        # when the digest records no feedback.
        if not self._done(n, "feedback"):
            if player_feedback(self._read_campaign(paths.rel(n, "digest"))):
                self._announce("feedback")
                project_feedback(self.root).mkdir(exist_ok=True)
                before = feedback_snapshot(self.root)
                self.backend.prompt(self.dm_sid, self.dm_agent,
                                    load("curate-feedback-brief").format(n=n))
                push_feedback(self.root, before)
            self._mark(n, "feedback")

        # Canon: new and changed entities, then the canon lint.
        if not self._done(n, "canon"):
            self._announce("canon")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-canon-brief").format(n=n))
            rr.lint_incomplete = len(apply_lint_correction(self.backend, self.dm_sid,
                                                           self.dm_agent, self.root))
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="lint", session=n,
                                       incomplete=rr.lint_incomplete,
                                       corrected=bool(rr.lint_incomplete))
            self._mark(n, "canon")

        # Arcs: one dispatch over the arcs not yet stamped for this session (all of them,
        # unless a resume finds some already done), then a coverage check read off the
        # stamps — one nudge naming any arc the pass missed.
        if not self._done(n, "arcs"):
            self._announce("arcs")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-arcs-brief").format(
                n=n, arcs=_bullets(arcs_not_stamped(self.root, n)),
                delegation=load(f"subagents-{load_settings(self.root).subagents}")))
            missed = arcs_not_stamped(self.root, n)
            if missed:
                self.backend.prompt(self.dm_sid, self.dm_agent, load("arcs-missed").format(
                    n=n, arcs=_bullets(missed)))
            rr.arcs_missed = tuple(missed)
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="arcs", session=n, missed=missed,
                                       still_missed=arcs_not_stamped(self.root, n))
            self._mark(n, "arcs")

        # State: the ledger, snapshots and the state dashboards.
        if not self._done(n, "state"):
            self._announce("state")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-state-brief").format(n=n))
            self._mark(n, "state")

        # Gate the whole apply, one bounded correction on the dm thread.
        if not self._done(n, "propagation"):
            self._announce("propagation")
            rr.propagation = self.gate.check_propagation(n)
            diff = correct_once(self.backend, self.dm_sid, self.dm_agent, rr.propagation, self.root)
            self._archive_stage("propagation", n, rr.propagation, diff)
            self._mark(n, "propagation")

        if commit and not self._done(n, "commit"):
            rr.committed = commit_campaign(self.root, f"campaign: post-session {n} updates")
            self._mark(n, "commit")

        # Plan session N+1 on the SAME dm thread (warm context), gated via the Planner.
        if prep and not self._done(n, "prep"):
            self._announce("prep")
            planner = Planner(self.backend, self.gate, dm_agent=self.dm_agent,
                              logs=self.logs, dm_sid=self.dm_sid)
            rr.prep = planner.prep_session(n + 1, commit=commit)
            self._mark(n, "prep")

        self._log(rr)
        if self.on_reconcile:
            self.on_reconcile(rr)
        return rr

    def _read_campaign(self, rel: str) -> str:
        try:
            p = self.root / "campaign" / rel
            return p.read_text(encoding="utf-8") if p.is_file() else ""
        except OSError:
            return ""

    def _archive_stage(self, stage: str, n: int, g, diff: str | None, **extra) -> None:
        """One `stage` score event, emitted as the stage completes — a crashed or
        resumed run archives exactly the stages that actually gated this run."""
        if self.logs and self.logs.archive:
            self.logs.archive.emit("stage", stage=stage, session=n,
                                   verdict=verdict_fields(g.narrative),
                                   corrected=diff is not None, diff=diff or "", **extra)

    def _log(self, rr: ReconcileResult) -> None:
        if self.logs:
            append(self.logs.checks, _format_block(rr))


def _format_block(rr: ReconcileResult) -> str:
    parts = [banner(f"RECONCILE session {rr.n}  ·  "
                    f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
                    f"{'committed' if rr.committed else 'uncommitted'}")]
    if rr.digest:
        parts.append(section(f"CHECK-DIGEST · {rr.digest.narrative.label}", rr.digest.narrative.report))
    if rr.lint_incomplete:
        parts.append(section("CANON LINT",
                             f"{rr.lint_incomplete} issue(s) after the canon pass; one correction dispatched."))
    if rr.arcs_missed:
        parts.append(section("ARC COVERAGE",
                             "Unstamped after the arc pass (one nudge sent): " + ", ".join(rr.arcs_missed)))
    if rr.propagation:
        parts.append(section(f"CHECK-PROPAGATION · {rr.propagation.narrative.label}",
                             rr.propagation.narrative.report))
    if rr.prep:
        parts.append(section(f"CHECK-PLAN (session {rr.prep.n}) · {rr.prep.gate.narrative.label}",
                             rr.prep.gate.narrative.report))
    parts.append("")
    return "\n\n".join(parts)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- `{i}`" for i in items) or "- (none left — every arc is already reconciled)"


_FEEDBACK_HEADING = re.compile(r"^#+\s*(?:\d+\.\s*)?player feedback\b.*$", re.I | re.M)
_NONE = re.compile(r"^[\s(_*—\"“-]*(?:none|n/?a|no feedback)\b[\s\w,.()—\"”-]*$", re.I)


def _marker_dir(root: Path) -> Path:
    return root / ".opencode" / ".orchestrator"


def prepped(root: Path | str, n: int) -> bool:
    """Whether session `n`'s wrap finished planning session n+1, its last stage."""
    return (_marker_dir(Path(root)) / f"reconcile-{n}-prep.done").is_file()


def player_feedback(digest: str) -> str:
    """The body of the digest's Player feedback section — '' when the section is missing,
    empty, or just says there was none."""
    m = _FEEDBACK_HEADING.search(digest)
    if not m:
        return ""
    rest = digest[m.end():]
    nxt = re.search(r"^#", rest, re.M)
    body = (rest[:nxt.start()] if nxt else rest).strip()
    return "" if _NONE.match(body) else body
