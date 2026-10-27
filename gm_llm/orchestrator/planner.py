"""
PRE-session planning — orchestrated.

  prep_session(N):
      dm authors campaign/sessions/N/plan.md                 # 1. the dm holds the pen
        (session 1: and prologue.md, one nudge if missing)
      canon lint on what it wrote, one correction
      result = gate.check_plan(plan, prologue)               # 2. ALWAYS gate, in code
      if result.violations: dm revises the file once         # 3. exactly ONE bounded pass
      commit "campaign: session N plan"                       # 4. deterministic commit
      return PrepResult

The dm authors and revises the file; the orchestrator owns *when* the gate runs and
*whether* to commit. A marker stands while planning runs, so a restart can tell a plan that
was cut off (`planning_cut_off`) from one that's ready to play.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .archive import verdict_fields
from .canon import dm_guidance
from .logs import append, banner, section
from . import paths
from .phase import apply_lint_correction, commit_campaign, correct_once
from .prompts import load


@dataclass
class PrepResult:
    n: int
    plan: str                  # the final plan text on disk
    gate: "StageGateResult"    # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool
    committed: bool
    draft: str = ""            # the plan as gated (== plan unless corrected)
    diff: str = ""             # what the correction changed under campaign/


class PlannerError(RuntimeError):
    pass


class Planner:
    """Drives the dm to prepare a session plan, gated in code."""

    def __init__(self, backend, gate, dm_agent: str = "dm",
                 on_prep=None, logs=None, dm_sid: str | None = None):
        self.backend = backend
        self.gate = gate
        self.dm_agent = dm_agent
        self.on_prep = on_prep
        self.logs = logs
        self.root = Path(backend.directory)
        # Reuse a caller's dm session when given (so the reconcile's apply thread carries
        # its warm context straight into prepping the next session); else open our own.
        self.dm_sid = dm_sid
        if not dm_sid:
            self.dm_sid = backend.create_session("dm prep")
            backend.preface(self.dm_sid, dm_guidance(self.root))

    def _plan_path(self, n: int) -> Path:
        return paths.plan(self.root / "campaign", n)

    def _read_plan(self, n: int) -> str:
        return _read(self._plan_path(n))

    def _read_prologue(self, n: int) -> str:
        return _read(paths.prologue(self.root / "campaign", n))

    def prep_session(self, n: int, commit: bool = False) -> PrepResult:
        # 1. The dm authors the plan file (and any new entities it pulls in). The first
        #    session also gets a prologue: the player remembers nothing before it.
        marker = _planning(self.root, n)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
        brief = load("plan-brief").format(n=n)
        if n == 1:
            brief += "\n\n" + load("prologue-brief")
        self.backend.prompt(self.dm_sid, self.dm_agent, brief)
        plan = self._read_plan(n)
        if not plan:
            raise PlannerError(
                f"the dm reported done but {self._plan_path(n)} is missing or empty")
        if n == 1 and not self._read_prologue(n):
            self.backend.prompt(self.dm_sid, self.dm_agent, load("setup-missing").format(
                missing=f"- `campaign/{paths.rel(n, 'prologue')}`, as the plan brief describes."))
        # New entities the plan pulled in meet the canon lint before the checker reads it.
        apply_lint_correction(self.backend, self.dm_sid, self.dm_agent, self.root)

        # 2. Gate it in code — always, narrative-only.
        result = self.gate.check_plan(plan, prologue=self._read_prologue(n))

        # 3. Exactly one bounded correction (no re-gate). Re-read the file after.
        draft = plan  # the text the gate judged — archived even once corrected over
        diff = correct_once(self.backend, self.dm_sid, self.dm_agent, result, self.root)
        corrected = diff is not None
        if corrected:
            plan = self._read_plan(n)

        # 4. Commit deterministically (the orchestrator owns git, not the model).
        committed = commit_campaign(self.root, f"campaign: session {n} plan") if commit else False
        marker.unlink()

        pr = PrepResult(n, plan, result, corrected, committed, draft=draft, diff=diff or "")
        self._log(pr)
        if self.on_prep:
            self.on_prep(pr)
        return pr

    def _log(self, pr: PrepResult) -> None:
        if self.logs:
            append(self.logs.checks, _format_block(pr))
        if self.logs and self.logs.archive:
            # Both plan texts ride along: `draft` is what the gate judged (what a
            # grader must read the verdict against), `plan` what landed on disk.
            # The reconcile stages' artifacts are all committed to the campaign
            # repo; a gated draft exists only here.
            self.logs.archive.emit(
                "stage", stage="plan", session=pr.n,
                verdict=verdict_fields(pr.gate.narrative),
                corrected=pr.corrected, committed=pr.committed,
                canon_sections=pr.gate.canon_sections,
                draft=pr.draft, plan=pr.plan, diff=pr.diff,
            )


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    except OSError:
        return ""


def _format_block(pr: PrepResult) -> str:
    g = pr.gate
    return "\n\n".join([
        banner(f"PREP session {pr.n}  ·  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
               f"{'CORRECTED' if pr.corrected else 'clean'}  ·  "
               f"{'committed' if pr.committed else 'uncommitted'}  ·  canon {g.canon_sections} sections"),
        section(f"CHECK-PLAN · {g.narrative.label}", g.narrative.report),
        "",
    ])


def _planning(root: Path | str, n: int) -> Path:
    return Path(root) / ".opencode" / ".orchestrator" / f"planning-{n}.pending"


def planning_cut_off(root: Path | str, n: int) -> bool:
    """Whether planning session `n` started and never finished: its plan isn't ready to play."""
    return _planning(root, n).is_file()
