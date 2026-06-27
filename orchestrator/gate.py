"""
The gate — run the two independent checks on a drafted turn, in code.

This is what the runner used to invoke as a tool; now the orchestrator owns it, so
it runs every turn by construction (never skipped) and the result is parsed
deterministically rather than sniffed from prose. Each checker's first line is a
machine-readable `VERDICT: PASS | VIOLATIONS`.

The narrative-checker (canon) gets the pre-loaded canon block; the rules-checker
(conduct) is canon-free and gets only the player's words + the draft. Both run as
fresh sessions per turn. The orchestrator supplies the player's message directly —
it owns the loop, so nothing has to fetch it from a transcript.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Verdict:
    agent: str
    passed: bool
    report: str  # full text, for the correction brief and logging


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
        parts = ["Notes on the narration you just wrote. Apply these fixes and output the corrected "
                 "narration only — change nothing else, and say nothing about the change.\n"]
        if not self.narrative.passed:
            parts.append("— Canon —\n" + self.narrative.report.strip())
        if not self.conduct.passed:
            parts.append("— Conduct —\n" + self.conduct.report.strip())
        return "\n\n".join(parts)


_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|VIOLATIONS)", re.I)


def parse_verdict(agent: str, text: str) -> Verdict:
    """Read the machine-readable verdict. Absent/garbled → fail safe to
    VIOLATIONS so the report still reaches the runner rather than slipping by."""
    for line in text.splitlines():
        m = _VERDICT_RE.search(line)
        if m:
            return Verdict(agent, m.group(1).upper() == "PASS", text)
    return Verdict(agent, passed=False, report=text)


def _narrative_brief(player_msg: str, canon: str, narration: str) -> str:
    return (
        "Role: check-turn. Verify the runner's drafted turn per your check-turn skill. The player's "
        "latest message below is what the player said this turn; the drafted turn is the narration "
        "about to be sent in response.\n\n"
        f"--- PLAYER'S LATEST MESSAGE (what the player said this turn) ---\n{player_msg}\n\n"
        f"{canon}"
        f"--- DRAFTED TURN ---\n{narration}"
    )


def _conduct_brief(player_msg: str, narration: str) -> str:
    return (
        "Check the runner's drafted turn for conduct violations. The player's latest message below is "
        "what the player said this turn; the drafted turn is the narration about to be sent in "
        "response.\n\n"
        f"--- PLAYER'S LATEST MESSAGE (what the player said this turn) ---\n{player_msg}\n\n"
        f"--- DRAFTED TURN ---\n{narration}"
    )


class Gate:
    def __init__(self, backend, preloader):
        self.backend = backend
        self.preloader = preloader

    def check(self, narration: str, player_msg: str) -> GateResult:
        canon = self.preloader.build(narration)
        # Serial, paced by the backend — keeps us off the rate limit that
        # parallel fan-out kept tripping.
        ns = self.backend.create_session("check-turn")
        n_out = self.backend.prompt(ns, "narrative-checker", _narrative_brief(player_msg, canon, narration))
        cs = self.backend.create_session("rules-check")
        c_out = self.backend.prompt(cs, "rules-checker", _conduct_brief(player_msg, narration))
        return GateResult(
            narrative=parse_verdict("narrative-checker", n_out),
            conduct=parse_verdict("rules-checker", c_out),
            player_msg=player_msg,
            canon_sections=canon.count("\n### "),
        )
