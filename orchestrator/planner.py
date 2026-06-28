"""
PRE-session planning — orchestrated.

The dm used to author the session plan and then *dispatch* the narrative-checker
itself (`check-plan` via the `task` tool) — model volition, the same shape we pulled
out of runtime. Here the orchestrator drives it deterministically, mirroring the
per-turn loop one stage earlier:

  prep_session(N):
      dm authors campaign/sessions/session-N-plan.md        # 1. the dm holds the pen
      result = gate.check_plan(plan)                         # 2. ALWAYS gate, in code
      if result.violations: dm revises the file once         # 3. exactly ONE bounded pass
      commit "campaign: session N plan"                       # 4. deterministic commit
      return PrepResult

The dm still authors and revises the file (it has write/edit); the orchestrator
owns *when* the gate runs and *whether* to commit — not the model. The authoring
brief tells the dm not to self-dispatch the checker or commit for this pass, so the
dm's standalone PRE-SESSION flow (used at init / post-session) is left untouched.

`Game` (loop.py) can then run the session the moment the plan exists — prep → play.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .phase import apply_one_correction, commit_campaign

_AUTHOR_BRIEF = (
    "Prepare session {n}. Run your PRE-SESSION planning pass: read current state and the active "
    "arc(s), identify which arc(s) to advance, then author the plan yourself into "
    "`campaign/sessions/session-{n}-plan.md`. Load `session-plan` and `canon-conventions`, work the "
    "completeness loop (author -> self-expand -> verify), and author + register every new entity the "
    "plan needs as a full file. Commit every load-bearing fact; leave open only the player's path.\n\n"
    "For this pass the plan is gated and committed FOR you: do NOT dispatch the narrative-checker "
    "yourself, and do NOT run git. When the plan file is written, stop and report only that it is "
    "ready — spoiler-free, no summary of its contents."
)


@dataclass
class PrepResult:
    n: int
    plan: str                  # the final plan text on disk
    gate: "PlanGateResult"     # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool
    committed: bool


class PlannerError(RuntimeError):
    pass


class Planner:
    """Drives the dm to prepare a session plan, gated in code."""

    def __init__(self, backend, gate, dm_agent: str = "dm",
                 on_prep=None, checks_log: str | None = None):
        self.backend = backend
        self.gate = gate
        self.dm_agent = dm_agent
        self.on_prep = on_prep
        self.checks_log = checks_log
        self.root = Path(backend.directory)
        self.dm_sid = backend.create_session("dm prep")

    def _plan_path(self, n: int) -> Path:
        return self.root / "campaign" / "sessions" / f"session-{n}-plan.md"

    def _read_plan(self, n: int) -> str:
        p = self._plan_path(n)
        try:
            return p.read_text() if p.is_file() else ""
        except OSError:
            return ""

    def prep_session(self, n: int, commit: bool = False) -> PrepResult:
        # 1. The dm authors the plan file (and any new entities it pulls in).
        self.backend.prompt(self.dm_sid, self.dm_agent, _AUTHOR_BRIEF.format(n=n))
        plan = self._read_plan(n)
        if not plan:
            raise PlannerError(
                f"the dm reported done but {self._plan_path(n)} is missing or empty")

        # 2. Gate it in code — always, narrative-only.
        result = self.gate.check_plan(plan)

        # 3. Exactly one bounded correction (no re-gate). Re-read the file after.
        corrected = apply_one_correction(self.backend, self.dm_sid, self.dm_agent, result)
        if corrected:
            plan = self._read_plan(n)

        # 4. Commit deterministically (the orchestrator owns git, not the model).
        committed = commit_campaign(self.root, f"campaign: session {n} plan") if commit else False

        pr = PrepResult(n, plan, result, corrected, committed)
        self._log(pr)
        if self.on_prep:
            self.on_prep(pr)
        return pr

    def _log(self, pr: PrepResult) -> None:
        if not self.checks_log:
            return
        try:
            with open(self.checks_log, "a") as f:
                f.write(_format_block(pr))
        except OSError:
            pass


def _sec(label: str, body: str) -> str:
    return f"\n  -- {label} {'-' * max(0, 68 - len(label))}\n\n{(body or '').strip()}\n"


def _format_block(pr: PrepResult) -> str:
    bar = "#" * 74
    g = pr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    return "\n\n".join([
        "", bar,
        f"  PREP session {pr.n}  ·  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
        f"{'CORRECTED' if pr.corrected else 'clean'}  ·  "
        f"{'committed' if pr.committed else 'uncommitted'}  ·  canon {g.canon_sections} sections",
        bar,
        _sec(f"CHECK-PLAN · {nv}", g.narrative.report),
        "",
    ])
