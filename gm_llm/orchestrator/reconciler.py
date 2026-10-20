"""
POST-session reconcile — the staged pipeline.

After a session, canon must absorb what was played. Rather than one fat `dm` call that
self-sequences the whole apply, the orchestrator dispatches each step as its own
focused, skill-loaded brief, gates the ones that warrant it in code, and applies at
most ONE bounded correction per gate — the same spine as a runtime turn, one stage out.

  reconcile_session(N):
    B  log-extractor: transcript -> digest         gate: check_digest
    C  analyst: digest -> assessment               (no gate)
    E  analyst: feedback -> campaign/feedback/*     gate: check_feedback
    D1 dm: new/changed entity canon                 completeness lint
    D2 dm: arc pass — one dispatch per arc (code-enumerated), then a close
       dispatch (new minor arcs + threads dashboard + sweep)
    D3 dm: ledger + state
       gate: check_propagation (the whole apply)
    commit "post-session N updates"
    F  dm (same thread): prep session N+1           gate: check_plan (via Planner)

The analyst thread is reused across C+E, the dm thread across D1-D3+F (so the apply's
warm context carries into prepping the next session). Each stage writes a marker under
`.orchestrator/` so a failed run resumes at the stage it died on instead of re-running
the non-idempotent apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import paths
from .archive import verdict_fields
from .backend import HEAVY_RETRIES, HEAVY_STALL_TIMEOUT
from .logs import append, banner, section
from .phase import apply_lint_correction, apply_one_correction, commit_campaign
from .registry import scan
from .planner import Planner, PrepResult  # noqa: F401 — PrepResult used in annotations
from .prompts import load


@dataclass
class ReconcileResult:
    n: int
    digest: "StageGateResult | None" = None       # noqa: F821 — annotation only
    feedback: "StageGateResult | None" = None     # noqa: F821
    propagation: "StageGateResult | None" = None  # noqa: F821
    lint_incomplete: int = 0      # entity files the D1 lint flagged (one correction dispatched)
    prep: "PrepResult | None" = None
    committed: bool = False


class Reconciler:
    """Drives the staged post-session apply, gated stage-by-stage in code."""

    def __init__(self, backend, gate, dm_agent: str = "dm",
                 analyst_agent: str = "campaign-analyst", extractor_agent: str = "log-extractor",
                 on_reconcile=None, on_stage=None, logs=None):
        self.backend = backend
        self.gate = gate
        self.dm_agent = dm_agent
        self.analyst_agent = analyst_agent
        self.extractor_agent = extractor_agent
        self.on_reconcile = on_reconcile
        self.on_stage = on_stage          # called with a stage key as each stage starts
        self.logs = logs
        self.root = Path(backend.directory)
        # One apply thread for the dm (D1-D3 + F), one for the analyst (C + E),
        # one for the extractor (B). Checker sessions are spawned per-call by the Gate.
        self.dm_sid = backend.create_session("dm apply")
        self.analyst_sid = backend.create_session("analyst")
        self.extractor_sid = backend.create_session("log-extractor")

    # -- stage markers (resume-after-failure) -------------------------------

    def _marker_dir(self) -> Path:
        return self.root / ".opencode" / ".orchestrator"

    def _marker(self, n: int, stage: str) -> Path:
        return self._marker_dir() / f"reconcile-{n}-{stage}.done"

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

        # B. Digest: transcript -> sessions/N/digest.md, gated for source-fidelity.
        if not self._done(n, "digest"):
            self._announce("digest")
            self.backend.prompt(self.extractor_sid, self.extractor_agent,
                                load("digest-brief").format(n=n))
            rr.digest = self.gate.check_digest(n)
            # The digest as gated, before the correction rewrites it in place — the
            # one reconcile artifact whose checked state never reaches a commit.
            draft = self._read_campaign(paths.rel(n, "digest"))
            corrected = apply_one_correction(self.backend, self.extractor_sid,
                                             self.extractor_agent, rr.digest)
            self._archive_stage("digest", n, rr.digest, corrected, draft=draft)
            self._mark(n, "digest")

        # C. Assessment (analyst): digest -> assessment. No gate — it's analysis, not canon.
        if not self._done(n, "assess"):
            self._announce("assess")
            self.backend.prompt(self.analyst_sid, self.analyst_agent,
                                load("assess-brief").format(n=n))
            self._mark(n, "assess")

        # E. Feedback (same analyst thread): curate campaign/feedback/*, gated.
        if not self._done(n, "feedback"):
            self._announce("feedback")
            self.backend.prompt(self.analyst_sid, self.analyst_agent,
                                load("curate-feedback-brief").format(n=n))
            rr.feedback = self.gate.check_feedback(n)
            corrected = apply_one_correction(self.backend, self.analyst_sid,
                                             self.analyst_agent, rr.feedback)
            self._archive_stage("feedback", n, rr.feedback, corrected)
            self._mark(n, "feedback")

        # D1. New/changed entity canon (dm), guarded by the completeness lint.
        if not self._done(n, "canon"):
            self._announce("canon")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-canon-brief").format(n=n))
            rr.lint_incomplete = self._lint_correct()
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="lint", session=n,
                                       incomplete=rr.lint_incomplete,
                                       corrected=bool(rr.lint_incomplete))
            self._mark(n, "canon")

        # D2. Arc pass (same dm thread): the orchestrator enumerates the arcs — code,
        # never the model — and dispatches each as its own focused brief; an untouched
        # arc is a cheap "no changes" turn. A final close dispatch creates any new
        # minor arc play birthed and reconciles the threads dashboard. The `arcs`
        # marker still means "whole pass done" (so a session reconciled before this
        # split never re-runs it); per-arc markers resume a mid-pass failure at the
        # arc it died on.
        if not self._done(n, "arcs"):
            self._announce("arcs")
            for slug in self._arc_slugs():
                if self._done(n, f"arcs-{slug}"):
                    continue
                self.backend.prompt(self.dm_sid, self.dm_agent,
                                    load("apply-arc-brief").format(n=n, slug=slug))
                self._mark(n, f"arcs-{slug}")
            self.backend.prompt(self.dm_sid, self.dm_agent,
                                load("apply-arcs-close-brief").format(n=n))
            self._mark(n, "arcs")

        # D3. Ledger + state (same dm thread).
        if not self._done(n, "state"):
            self._announce("state")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-state-brief").format(n=n))
            self._mark(n, "state")

        # Gate the whole apply (D1-D3), one bounded correction on the dm thread.
        if not self._done(n, "propagation"):
            self._announce("propagation")
            rr.propagation = self.gate.check_propagation(n)
            corrected = apply_one_correction(self.backend, self.dm_sid,
                                             self.dm_agent, rr.propagation)
            self._archive_stage("propagation", n, rr.propagation, corrected)
            self._mark(n, "propagation")

        # Commit the post-session updates (digest, assessment, feedback, canon, arcs, state).
        if commit and not self._done(n, "commit"):
            rr.committed = commit_campaign(self.root, f"campaign: post-session {n} updates")
            self._mark(n, "commit")

        # F. Prep session N+1 on the SAME dm thread (warm context), gated via the Planner.
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

    def _arc_slugs(self) -> list[str]:
        """Every arc on disk — the per-arc dispatch list, enumerated in code."""
        return sorted(e.slug for e in scan(self.root / "campaign") if e.type == "arc")

    def _lint_correct(self) -> int:
        """Run the canon lint after the canon pass; one bounded correction if it found
        anything. Returns the count of issues found (0 if clean)."""
        return len(apply_lint_correction(self.backend, self.dm_sid, self.dm_agent, self.root))

    def _read_campaign(self, rel: str) -> str:
        try:
            p = self.root / "campaign" / rel
            return p.read_text(encoding="utf-8") if p.is_file() else ""
        except OSError:
            return ""

    def _archive_stage(self, stage: str, n: int, g, corrected: bool, **extra) -> None:
        """One `stage` score event, emitted as the stage completes — a crashed or
        resumed run archives exactly the stages that actually gated this run."""
        if self.logs and self.logs.archive:
            self.logs.archive.emit("stage", stage=stage, session=n,
                                   verdict=verdict_fields(g.narrative),
                                   corrected=corrected, **extra)

    def _log(self, rr: ReconcileResult) -> None:
        if self.logs:
            append(self.logs.checks, _format_block(rr))


def _format_block(rr: ReconcileResult) -> str:
    parts = [banner(f"RECONCILE session {rr.n}  ·  "
                    f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
                    f"{'committed' if rr.committed else 'uncommitted'}")]
    if rr.digest:
        parts.append(section(f"CHECK-DIGEST · {rr.digest.narrative.label}", rr.digest.narrative.report))
    if rr.feedback:
        parts.append(section(f"CHECK-FEEDBACK · {rr.feedback.narrative.label}", rr.feedback.narrative.report))
    if rr.lint_incomplete:
        parts.append(section("COMPLETENESS LINT",
                             f"{rr.lint_incomplete} entity file(s) incomplete after D1; one correction dispatched."))
    if rr.propagation:
        parts.append(section(f"CHECK-PROPAGATION · {rr.propagation.narrative.label}",
                             rr.propagation.narrative.report))
    if rr.prep:
        parts.append(section(f"CHECK-PLAN (session {rr.prep.n}) · {rr.prep.gate.narrative.label}",
                             rr.prep.gate.narrative.report))
    parts.append("")
    return "\n\n".join(parts)
