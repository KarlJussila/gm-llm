"""
MockGame — a stand-in for the real Game so interfaces (the TUI, tests) can run
without a backend or model calls. Duck-types Game's start()/turn()/meta() and
returns scripted TurnResults, cycling through clean / corrected / violation states
so the UI exercises every path. No opencode, no rate limit.
"""

from __future__ import annotations

from .gate import GateResult, Verdict
from .loop import TurnResult

_OPENING = (
    "The Crossroads Inn is warm and loud — low beams, smoke, a dozen faces turning as the door bangs "
    "shut. Behind the bar a broad-shouldered man with grey-streaked hair works a rag over a mug. The "
    "satchel at your hip stirs.\n\nReady when you are."
)


class MockGame:
    def __init__(self, *args, **kwargs):
        self.runner_sid = "mock-runner"
        self._n = 0

    def start(self, kickoff: str = "Let's begin the session.") -> TurnResult:
        return self._result(_OPENING, kickoff, clean=True)

    def turn(self, player_input: str) -> TurnResult:
        self._n += 1
        corrected = self._n % 3 == 0  # every third turn exercises the correction path
        narration = (
            f"Magren's gaze flicks to you, then the satchel. \"That glow,\" he says. \"Not the first "
            f"I've seen.\" He slides a mug across the bar. (mock reply to: “{player_input[:60]}”)"
        )
        return self._result(narration, player_input, clean=not corrected, corrected=corrected)

    def meta(self, question: str) -> str:
        return "(out-of-game) We can wrap at the next natural beat — no rush."

    def _result(self, narration, player_msg, clean=True, corrected=False) -> TurnResult:
        narrative = Verdict(
            "narrative-checker", clean,
            "VERDICT: PASS" if clean else
            "VERDICT: VIOLATIONS\n1. Magren's hair is grey-streaked, not black — fix the description "
            "(source: world/npcs/magren-soley.md).",
        )
        conduct = Verdict("rules-checker", True, "VERDICT: PASS")
        gate = GateResult(narrative, conduct, player_msg, canon_sections=9)
        draft = ("(pre-correction draft) " + narration) if corrected else narration
        return TurnResult(player_msg, draft, narration, gate, corrected)
