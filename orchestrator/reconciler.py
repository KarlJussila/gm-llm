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
    D2 dm: arc pass
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

from . import completeness
from .logs import append, banner, section
from .phase import apply_one_correction, commit_campaign
from .planner import Planner, PrepResult  # noqa: F401 — PrepResult used in annotations
from .prompts import load


@dataclass
class ReconcileResult:
    n: int
    digest: "DigestGateResult | None" = None        # noqa: F821 — annotation only
    feedback: "FeedbackGateResult | None" = None     # noqa: F821
    propagation: "PropagationGateResult | None" = None  # noqa: F821
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
                datetime.now(timezone.utc).isoformat(timespec="seconds"))
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
        if fresh:
            self.clear_markers(n)
        rr = ReconcileResult(n)

        # B. Digest: transcript -> session-N.md, gated for source-fidelity.
        if not self._done(n, "digest"):
            self._announce("digest")
            self.backend.prompt(self.extractor_sid, self.extractor_agent,
                                load("digest-brief").format(n=n))
            rr.digest = self.gate.check_digest(n)
            apply_one_correction(self.backend, self.extractor_sid, self.extractor_agent, rr.digest)
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
            apply_one_correction(self.backend, self.analyst_sid, self.analyst_agent, rr.feedback)
            self._mark(n, "feedback")

        # D1. New/changed entity canon (dm), guarded by the completeness lint.
        if not self._done(n, "canon"):
            self._announce("canon")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-canon-brief").format(n=n))
            rr.lint_incomplete = self._lint_correct()
            self._mark(n, "canon")

        # D2. Arc pass (same dm thread).
        if not self._done(n, "arcs"):
            self._announce("arcs")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("apply-arcs-brief").format(n=n))
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
            apply_one_correction(self.backend, self.dm_sid, self.dm_agent, rr.propagation)
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

    def _lint_correct(self) -> int:
        """Run the completeness lint after D1; if anything is incomplete, dispatch ONE
        bounded correction to the dm with the missing fields (no re-lint loop). Returns
        the count of incomplete files found (0 if clean)."""
        bad = [r for r in completeness.lint_dir(self.root) if not r.ok]
        if not bad:
            return 0
        lines = []
        for r in bad:
            rel = r.path.relative_to(self.root)
            missing = list(r.missing) + [f"{s} (section)" for s in r.missing_sections]
            lines.append(f"- {rel} [{r.type}]: {', '.join(missing)}")
        self.backend.prompt(self.dm_sid, self.dm_agent,
                            load("correct-completeness") + "\n\n— Incomplete —\n" + "\n".join(lines))
        return len(bad)

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
