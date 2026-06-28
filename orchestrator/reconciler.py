"""
POST-session reconcile — orchestrated.

After the player finishes a session, the canon has to absorb what happened: extract
the transcript into the digest, then from that digest author the new-canon files +
registry rows, reconcile the arc bodies (a real revision, not a status bump), flip
the ledger, and update every state snapshot. That apply pass is the `dm`'s — it
holds the pen and delegates `log-extractor` / `campaign-analyst` as it needs them.

What was *never* wired is the gate: `check-propagation` existed as a skill but no
flow ran it. The orchestrator wires it the right way — in code, not by model
volition — exactly as PRE planning does one stage earlier:

  reconcile_session(N):
      dm runs the apply pass for session N                  # 1. the dm holds the pen
      result = gate.check_propagation(N)                    # 2. ALWAYS gate, in code
      if result.violations: dm backfills the gaps once       # 3. exactly ONE bounded pass
      commit "campaign: post-session N updates"              # 4. deterministic commit
      return ReconcileResult

The orchestrator can then sequence reconcile(N) -> prep(N+1) (the Planner) to turn a
played session into the next ready one. The dm's standalone POST flow is untouched;
the authoring brief just tells it not to gate, commit, or prep the next session for
this pass — those the orchestrator owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .phase import apply_one_correction, commit_campaign

_APPLY_BRIEF = (
    "Reconcile session {n} now — the player has finished it. Run your POST-SESSION apply pass: "
    "extract the transcript into the digest (`campaign/sessions/session-{n}.md`, delegate "
    "`log-extractor`), then from that digest author + register every new-canon entity/world file, "
    "reconcile each affected arc body (a real revision, not a status bump), flip the ledger "
    "(`[hidden]` -> `[revealed: S{n}]`, `Known to:`), update all state snapshots, route any verbatim "
    "documents, and distill the player's feedback into `campaign/feedback/`. Work the completeness "
    "loop; leave nothing the session established unfiled.\n\n"
    "For this pass the result is gated and committed FOR you, and the next session is prepped "
    "separately: do NOT run check-propagation yourself, do NOT run git, and do NOT prepare session "
    "{next_n}. When the apply pass is done, stop and report only that it is reconciled — spoiler-free."
)


@dataclass
class ReconcileResult:
    n: int
    gate: "PropagationGateResult"   # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool
    committed: bool


class Reconciler:
    """Drives the dm to apply a played session into canon, gated in code."""

    def __init__(self, backend, gate, dm_agent: str = "dm",
                 on_reconcile=None, checks_log: str | None = None):
        self.backend = backend
        self.gate = gate
        self.dm_agent = dm_agent
        self.on_reconcile = on_reconcile
        self.checks_log = checks_log
        self.root = Path(backend.directory)
        self.dm_sid = backend.create_session("dm reconcile")

    def reconcile_session(self, n: int, commit: bool = False) -> ReconcileResult:
        # 1. The dm runs the apply pass (digest, canon, arcs, state, ledger, feedback).
        self.backend.prompt(self.dm_sid, self.dm_agent,
                            _APPLY_BRIEF.format(n=n, next_n=n + 1))

        # 2. Gate it in code — always, narrative-only, a whole-repo propagation audit.
        result = self.gate.check_propagation(n)

        # 3. Exactly one bounded correction (no re-gate).
        corrected = apply_one_correction(self.backend, self.dm_sid, self.dm_agent, result)

        # 4. Commit deterministically (the orchestrator owns git, not the model).
        committed = commit_campaign(self.root, f"campaign: post-session {n} updates") if commit else False

        rr = ReconcileResult(n, result, corrected, committed)
        self._log(rr)
        if self.on_reconcile:
            self.on_reconcile(rr)
        return rr

    def _log(self, rr: ReconcileResult) -> None:
        if not self.checks_log:
            return
        try:
            with open(self.checks_log, "a") as f:
                f.write(_format_block(rr))
        except OSError:
            pass


def _sec(label: str, body: str) -> str:
    return f"\n  -- {label} {'-' * max(0, 68 - len(label))}\n\n{(body or '').strip()}\n"


def _format_block(rr: ReconcileResult) -> str:
    bar = "#" * 74
    g = rr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    return "\n\n".join([
        "", bar,
        f"  RECONCILE session {rr.n}  ·  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
        f"{'CORRECTED' if rr.corrected else 'clean'}  ·  "
        f"{'committed' if rr.committed else 'uncommitted'}",
        bar,
        _sec(f"CHECK-PROPAGATION · {nv}", g.narrative.report),
        "",
    ])
