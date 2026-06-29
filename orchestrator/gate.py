"""
The gate — run the independent checks on drafted content, in code.

This is what the runner (and the dm, at planning) used to invoke as a tool; now the
orchestrator owns it, so it runs by construction (never skipped) and the result is
parsed deterministically rather than sniffed from prose. Each checker ends with a
machine-readable `VERDICT: PASS | VIOLATIONS` on its last line.

Three shapes share one spawn-and-parse engine:
  - `check(narration, player_msg)` — the RUNTIME gate: narrative-checker (canon,
    with the pre-loaded canon block) + rules-checker (conduct, canon-free, only the
    player's words + the draft). The orchestrator supplies the player's message
    directly — it owns the loop, so nothing has to fetch it from a transcript.
  - `check_plan(plan)` — the PRE gate: narrative-checker only (a plan has no
    conduct to police and no player message), with the pre-loaded canon block.
  - `check_propagation(n)` — the POST gate: narrative-checker only, verifying that
    session N's updates landed in canon and state. No preload — the checker reads
    N's digest against the updated files itself; there's no single draft to match
    names against.

Each checker runs as a fresh session per call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .prompts import load


@dataclass
class Verdict:
    agent: str
    passed: bool
    report: str  # full text, for the correction brief and logging
    empty_violation: bool = False  # stamped VIOLATIONS with no findings → downgraded to pass

    @property
    def label(self) -> str:
        """Human label for logs/UI, distinguishing a real pass from a downgraded one."""
        if self.empty_violation:
            return "PASS (empty VIOLATIONS — checker gave no findings)"
        return "PASS" if self.passed else "VIOLATIONS"


@dataclass
class GateResult:
    narrative: Verdict
    conduct: Verdict
    player_msg: str
    canon_sections: int

    @property
    def violations(self) -> bool:
        return not (self.narrative.passed and self.conduct.passed)

    def correction_brief(self) -> str:
        """The message handed back to the runner to revise its narration."""
        parts = [load("correct-turn") + "\n"]
        if not self.narrative.passed:
            parts.append("— Canon —\n" + self.narrative.report.strip())
        if not self.conduct.passed:
            parts.append("— Conduct —\n" + self.conduct.report.strip())
        return "\n\n".join(parts)


@dataclass
class PlanGateResult:
    narrative: Verdict
    canon_sections: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the dm to revise the plan file it just wrote."""
        return load("correct-plan") + "\n\n— Canon —\n" + self.narrative.report.strip()


@dataclass
class PropagationGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the dm to backfill the gaps from its apply pass."""
        return (load("correct-propagation").format(session=self.session)
                + "\n\n— Propagation —\n" + self.narrative.report.strip())


@dataclass
class DigestGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the digest's author (log-extractor) to fix it."""
        return (load("correct-digest").format(session=self.session)
                + "\n\n— Digest —\n" + self.narrative.report.strip())


@dataclass
class FeedbackGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the feedback curator (analyst) to fix the files."""
        return (load("correct-feedback").format(session=self.session)
                + "\n\n— Feedback —\n" + self.narrative.report.strip())


_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|VIOLATIONS)", re.I)


def parse_verdict(agent: str, text: str) -> Verdict:
    """Read the machine-readable verdict, which the checkers emit on their LAST
    line (a modest model concludes after working its steps). We scan bottom-up and
    take the last match, so a stray earlier mention (a quoted example, a step note)
    can't pre-empt the real verdict. Absent/garbled → fail safe to VIOLATIONS so the
    report still reaches the caller rather than slipping by.

    Guard: a `VIOLATIONS` verdict with **no findings body** (just the verdict line,
    nothing above it) is not actionable — there's nothing for the caller to fix — so
    we treat it as a pass. Modest models sometimes stamp the verdict without listing
    anything; without this, that fires a content-free correction."""
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        m = _VERDICT_RE.search(lines[i])
        if m:
            passed = m.group(1).upper() == "PASS"
            empty = not passed and not "\n".join(lines[:i] + lines[i + 1:]).strip()
            if empty:
                passed = True  # VIOLATIONS with an empty body → nothing to act on
            return Verdict(agent, passed, text, empty_violation=empty)
    return Verdict(agent, passed=False, report=text)


def _narrative_brief(player_msg: str, canon: str, narration: str) -> str:
    return load("check-turn-brief").format(player_msg=player_msg, canon=canon, narration=narration)


def _conduct_brief(player_msg: str, narration: str) -> str:
    return load("check-conduct-brief").format(player_msg=player_msg, narration=narration)


def _plan_brief(plan: str, canon: str) -> str:
    return load("check-plan-brief").format(plan=plan, canon=canon)


def _propagation_brief(n: int) -> str:
    return load("check-propagation-brief").format(n=n)


def _digest_brief(n: int) -> str:
    return load("check-digest-brief").format(n=n)


def _feedback_brief(n: int) -> str:
    return load("check-feedback-brief").format(n=n)


class Gate:
    def __init__(self, backend, preloader):
        self.backend = backend
        self.preloader = preloader

    def _run(self, title: str, agent: str, brief: str) -> Verdict:
        """Spawn a fresh checker session, prompt it, parse its VERDICT line.
        Serial and paced by the backend — keeps us off the rate limit that
        parallel fan-out kept tripping. `whole=True`: a checker runs a todowrite
        list then reports, so its findings and verdict can span text parts — we
        need all of them, not just the last."""
        sid = self.backend.create_session(title)
        return parse_verdict(agent, self.backend.prompt(sid, agent, brief, whole=True))

    def check(self, narration: str, player_msg: str) -> GateResult:
        canon = self.preloader.build(narration)
        return GateResult(
            narrative=self._run("check-turn", "narrative-checker",
                                _narrative_brief(player_msg, canon, narration)),
            conduct=self._run("rules-check", "rules-checker",
                              _conduct_brief(player_msg, narration)),
            player_msg=player_msg,
            canon_sections=canon.count("\n### "),
        )

    def check_plan(self, plan: str) -> PlanGateResult:
        """The PRE gate: narrative-only check of a draft session plan. The plan text
        drives the canon preload exactly as a draft turn does (names match by name)."""
        canon = self.preloader.build(plan)
        return PlanGateResult(
            narrative=self._run("check-plan", "narrative-checker", _plan_brief(plan, canon)),
            canon_sections=canon.count("\n### "),
        )

    def check_propagation(self, n: int) -> PropagationGateResult:
        """The POST gate: narrative-only check that session N's apply pass landed
        everywhere. No preload — propagation is a whole-repo audit (the digest vs.
        the updated files), not a single draft, so the checker reads on demand."""
        return PropagationGateResult(
            narrative=self._run("check-propagation", "narrative-checker", _propagation_brief(n)),
            session=n,
        )

    def check_digest(self, n: int) -> DigestGateResult:
        """The first POST gate: the digest vs. the transcript. No preload —
        source-fidelity (did the extraction keep faith with what was played), which
        the checker reads on demand, not a canon comparison."""
        return DigestGateResult(
            narrative=self._run("check-digest", "narrative-checker", _digest_brief(n)),
            session=n,
        )

    def check_feedback(self, n: int) -> FeedbackGateResult:
        """A POST gate: the curated feedback files vs. the player's actual words. No
        preload — the checker reads the digest's feedback section and the feedback
        files on demand."""
        return FeedbackGateResult(
            narrative=self._run("check-feedback", "narrative-checker", _feedback_brief(n)),
            session=n,
        )
