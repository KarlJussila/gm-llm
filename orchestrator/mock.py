"""
MockGame — a stand-in for the real Game so interfaces (the TUI, tests) can run
without a backend or model calls. Duck-types Game's start()/turn()/meta() and
returns scripted TurnResults, cycling through clean / corrected / violation states
so the UI exercises every path. No opencode, no rate limit.
"""

from __future__ import annotations

import time

from .gate import GateResult, Verdict
from .loop import TurnResult
from .setup import SetupTurn

_WRAP_STAGES = ["digest", "assess", "feedback", "canon", "arcs", "state", "propagation", "prep"]

_SETUP_SCRIPT = [
    "Welcome — let's build a campaign. What kind would you like to play? You can describe what "
    "you're after to any level of detail, or we can do a guided setup where I ask a few questions. "
    "Whatever you prefer.",
    "A rain-soaked harbour city run by rival guilds — love it. What tone are you after: bleak and "
    "hard-boiled, or something pulpier with room to breathe?",
    "Perfect. Tell me about who you'll play — a concept, a class, or just a vibe.",
    "Great character. I've got what I need — building the world, your arcs, and the opening around "
    "you now. One moment.",
]

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
        time.sleep(1.5)  # let the heartbeat tick so the UI is testable offline
        return self._result(_OPENING, kickoff, clean=True)

    def resume(self) -> str | None:
        return None  # mock always opens fresh

    def turn(self, player_input: str) -> TurnResult:
        time.sleep(1.5)  # let the heartbeat tick so the UI is testable offline
        self._n += 1
        corrected = self._n % 3 == 0  # every third turn exercises the correction path
        narration = (
            f"Magren's gaze flicks to you, then the satchel. \"That glow,\" he says. \"Not the first "
            f"I've seen.\" He slides a mug across the bar. (mock reply to: “{player_input[:60]}”)"
        )
        return self._result(narration, player_input, clean=not corrected, corrected=corrected)

    def meta(self, question: str) -> str:
        time.sleep(1.5)  # let the heartbeat tick so the UI is testable offline
        return "(out-of-game) We can wrap at the next natural beat — no rush."

    def abort(self) -> bool:
        return False  # mock turns resolve instantly — nothing in flight to cancel

    def revert_last_turn(self) -> bool:
        return False  # no backend session to roll back

    def _result(self, narration, player_msg, clean=True, corrected=False) -> TurnResult:
        narrative = Verdict(
            "narrative-checker", clean,
            "" if clean else
            "1. Magren's hair is grey-streaked, not black — fix the description "
            "(source: world/npcs/magren-soley.md).",
        )
        conduct = Verdict("check-conduct", True, "")
        gate = GateResult(narrative, conduct, player_msg, canon_sections=9)
        draft = ("(pre-correction draft) " + narration) if corrected else narration
        return TurnResult(player_msg, draft, narration, gate, corrected)


class MockSetup:
    """Stand-in for Setup: a scripted new-campaign conversation that reports done after
    a few exchanges, so the TUI setup path runs offline."""

    def __init__(self, *args, **kwargs):
        self.dm_sid = "mock-setup"
        self._n = 0

    def start(self) -> SetupTurn:
        return SetupTurn(_SETUP_SCRIPT[0], False)

    def turn(self, player_input: str) -> SetupTurn:
        self._n += 1
        i = min(self._n, len(_SETUP_SCRIPT) - 1)
        done = self._n >= len(_SETUP_SCRIPT) - 1
        return SetupTurn(_SETUP_SCRIPT[i], done)

    def finalize(self) -> int:
        return 1


class _NoTap:
    def stop(self) -> None:
        pass


class MockLifecycle:
    """Stand-in for Lifecycle: a MockGame plus a simulated wrap() (and an optional
    setup phase) so the TUI's full flow can be driven offline."""

    def __init__(self, start_in_setup: bool = False, *args, **kwargs):
        self._session = 1
        if start_in_setup:
            self.phase = "setup"
            self.game = None
            self.setup = MockSetup()
        else:
            self.phase = "play"
            self.game = MockGame()
            self.setup = None

    @property
    def session(self) -> int:
        return self._session

    def setup_stream(self, stream_write, on_tool=None):
        return _NoTap()

    def play_stream(self, stream_write):
        if not stream_write:
            return None
        return _NoTap()

    def finish_setup(self, on_stage=None, stream_write=None) -> int:
        if on_stage:
            on_stage("prep")
        if stream_write:
            stream_write("[bold cyan]\n──── planning session 1 ────\n[/]")
            stream_write("  (mock) writing the session-1 plan…\n")
        time.sleep(0.6)
        self.phase = "play"
        self.game = MockGame()
        self.setup = None
        return self._session

    def wrap(self, on_stage=None, stream_write=None, commit: bool = True) -> int:
        for key in _WRAP_STAGES:
            if on_stage:
                on_stage(key)
            if stream_write:
                # Mirror the live EventTap's markup dialect so the offline demo shows
                # the same coloured headings / tool lines the real stream produces.
                stream_write(f"[bold cyan]\n──── {key} ────\n[/]")
                stream_write(f"  (mock) working {key}…\n")
                stream_write(f"[yellow]  ⚙ {key}: write  world/notes/{key}.md[/]\n")
            time.sleep(0.6)  # let the ticker breathe so the flow is visible
        self._session += 1
        self.game = MockGame()
        return self._session
