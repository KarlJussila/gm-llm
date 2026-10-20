"""
MockGame — a stand-in for the real Game so interfaces (the TUI, tests) can run
without a backend or model calls. Duck-types Game's start()/turn()/meta() and
returns scripted TurnResults, cycling through clean / corrected / violation states
so the UI exercises every path. No opencode, no rate limit.

The mock mirrors every seam the TUI wires: the per-turn `on_step` ticker, a
`backend.on_retry` notice (turn 4), a session-complete ending (turn 6), and
cancellable sleeps (`abort()` raises `BackendCancelled` out of the in-flight
call, like the real Backend) — so the whole UI is testable offline.
"""

from __future__ import annotations

import time
from pathlib import Path

from .backend import BackendCancelled
from .combat import CombatStep
from .gate import GateResult, Verdict
from .loop import TurnResult
from .setup import SetupTurn
from .status import CampaignStatus

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

_CLOSING = (
    "Magren bolts the door behind the last regular and snuffs the lamps one by one. \"Get some "
    "sleep,\" he says. \"Whatever that satchel wants of you, it'll still want it tomorrow.\" The "
    "night takes the harbour quiet, for once.\n\n— a good place to rest —"
)

# A short scripted combat episode (design/combat.md) so the offline TUI can demo the initiative
# loop — enter on a normal turn (`combat_started`), a PC slot, two NPC beats each awaiting
# confirm, then the fight ends and normal play resumes.
_COMBAT_ENTER = (
    "The door bangs open and two dockside toughs shoulder in, blades already out. One vaults "
    "the bar toward Magren; the other comes straight at you. Steel scrapes free — roll for "
    "initiative."
)
_COMBAT_PC = (
    "You read the nearer thug's footing and strike as he closes — a clean opening. (Roll your "
    "attack when you're ready.)"
)
_COMBAT_NPC1 = (
    "The thug you cut staggers, then slashes back low — his blade skids off your guard, but the "
    "force of it rocks you a step toward the hearth. He's 5 ft in front of you, breathing hard."
)
_COMBAT_NPC1_BLUNTED = (
    "Your shield snaps up as the thug slashes low — the blade rings off the boss and skitters "
    "wide. He's 5 ft in front of you, wrong-footed now, breathing hard."
)
_COMBAT_NPC2 = (
    "Behind the bar, the second tough feints at Magren, then hurls a stool your way — it clips "
    "your shoulder and clatters past. He's 15 ft NE, using the bar as cover."
)
_COMBAT_END = (
    "The nearer thug sees his partner falter, spits a curse, and both of them break for the "
    "door, boots pounding the wet boards into the dark. The commons lets out its held breath. "
    "Magren sets a cudgel back under the bar. \"Friends of yours?\""
)


class _MockBackend:
    """Just enough backend surface for the TUI's unconditional wiring: a retry
    hook to render and an abort() for the cancel path (the real cancel signal
    lives on MockGame; this abort only reports nothing-in-flight)."""

    def __init__(self):
        self.on_retry = None
        self.retries = 4  # mirrors Backend's default, read by the retry-notice renderer

    def abort(self) -> bool:
        return False


class MockGame:
    def __init__(self, backend=None, *args, pace: float = 1.0, **kwargs):
        self.runner_sid = "mock-runner"
        self.backend = backend or _MockBackend()
        self.on_step = None  # the TUI assigns this, same as on the real Game
        # Every sleep below is scaled by `pace`: 1.0 is the watchable demo the offline TUI
        # is for, 0 runs the same script as fast as the machine will go (dev/test_tui_loop.py
        # drives the real app over it — a scripted delay is scenery, not behavior).
        self.pace = pace
        self._n = 0
        self._abort = False
        self._in_combat = False
        self._combat_phase = 0            # scripted position in the combat episode
        self._combat_pending = None       # the NPC beat awaiting confirm

    @property
    def in_combat(self) -> bool:
        return self._in_combat

    def _step(self, key: str) -> None:
        if self.on_step:
            try:
                self.on_step(key)
            except Exception:  # noqa: BLE001 — same best-effort contract as the real Game
                pass

    def _sleep(self, seconds: float) -> None:
        """A cancellable sleep: abort() flips the flag and the in-flight call raises
        BackendCancelled, mirroring the real Backend's cancel semantics."""
        if self._abort:  # cancelled before the call even settled in
            self._abort = False
            raise BackendCancelled("mock call cancelled")
        deadline = time.monotonic() + seconds * self.pace
        while time.monotonic() < deadline:
            if self._abort:
                self._abort = False
                raise BackendCancelled("mock call cancelled")
            time.sleep(0.05)

    def start(self, kickoff: str = "Let's begin the session.") -> TurnResult:
        self._step("draft")
        self._sleep(1.0)
        self._step("check")
        self._sleep(0.5)
        self._step("done")
        return self._result(_OPENING, kickoff, clean=True)

    def resume(self) -> str | None:
        return None  # mock always opens fresh

    def turn(self, player_input: str) -> TurnResult:
        self._n += 1
        corrected = self._n % 3 == 0   # every third turn exercises the correction path
        ending = self._n % 6 == 0      # every sixth turn ends the session (the wrap prompt)
        starting_combat = self._n == 2  # turn 2 kicks off the scripted combat episode
        try:
            self._step("draft")
            if self._n % 4 == 0 and self.backend.on_retry:  # turn 4 exercises the retry notice
                self.backend.on_retry("dm-runner", 1, 5, "429 (mock)")
                self._sleep(1.0)
            self._sleep(0.8)
            self._step("check")
            self._sleep(0.5)
            if corrected:
                self._step("correct")
                self._sleep(0.5)
            self._step("done")
        except BackendCancelled:
            self._n -= 1  # a cancelled turn is reverted — it doesn't consume a script slot
            raise
        if starting_combat:
            self._in_combat = True
            self._combat_phase = 0
            return self._result(_COMBAT_ENTER, player_input, clean=True, combat_started=True)
        narration = _CLOSING if ending else (
            f"Magren's gaze flicks to you, then the satchel. \"That glow,\" he says. \"Not the first "
            f"I've seen.\" He slides a mug across the bar. (mock reply to: “{player_input[:60]}”)"
        )
        return self._result(narration, player_input, clean=not corrected,
                            corrected=corrected, session_complete=ending)

    # -- combat surface (scripted; drives the offline CombatDriver demo) -------

    def combat_step(self) -> CombatStep:
        """Emit the next scripted combat beat. Mirrors the real Game's contract: a PC slot
        (`await_pc`), an NPC beat awaiting confirm (`await_confirm`), or the fight's end
        (`ended`, which drops out of combat)."""
        phase = self._combat_phase
        if phase == 0:
            return CombatStep(kind="await_pc", combatant="pc", round=1)
        if phase == 1:
            self._sleep(0.7)
            self._combat_pending = CombatStep(kind="await_confirm", combatant="thug-1",
                                              round=1, narration=_COMBAT_NPC1)
            return self._combat_pending
        if phase == 2:
            self._sleep(0.7)
            self._combat_pending = CombatStep(kind="await_confirm", combatant="thug-2",
                                              round=1, narration=_COMBAT_NPC2)
            return self._combat_pending
        self._in_combat = False
        self._combat_pending = None
        return CombatStep(kind="ended", narration=_COMBAT_END)

    def combat_player_action(self, player_input: str) -> CombatStep:
        self._step("draft")
        self._sleep(0.6)
        self._step("done")
        self._combat_phase = 1
        return CombatStep(kind="committed", combatant="pc", round=1, narration=_COMBAT_PC)

    def combat_confirm(self) -> CombatStep | None:
        step = self._combat_pending
        self._combat_pending = None
        self._combat_phase += 1
        return step

    def combat_interject(self, text: str) -> CombatStep:
        """Replay the pending NPC beat with the reaction folded in — the same combatant,
        blunted. Re-presented for confirm, like the real Game."""
        self._step("draft")
        self._sleep(0.5)
        self._step("done")
        self._combat_pending = CombatStep(kind="await_confirm", combatant="thug-1",
                                          round=1, narration=_COMBAT_NPC1_BLUNTED)
        return self._combat_pending

    def meta(self, question: str) -> str:
        self._sleep(1.5)
        return "(out-of-game) We can wrap at the next natural beat — no rush."

    def abort(self) -> bool:
        self._abort = True  # the in-flight _sleep raises BackendCancelled
        return True

    def revert_last_turn(self) -> bool:
        return False  # no backend session to roll back

    def _result(self, narration, player_msg, clean=True, corrected=False,
                session_complete=False, combat_started=False) -> TurnResult:
        narrative = Verdict(
            "check-turn", clean,
            "" if clean else
            "1. Magren's hair is grey-streaked, not black — fix the description "
            "(source: world/npcs/magren-soley.md).",
        )
        conduct = Verdict("check-conduct", True, "")
        gate = GateResult(narrative, conduct, player_msg, canon_sections=9)
        draft = ("(pre-correction draft) " + narration) if corrected else narration
        return TurnResult(player_msg, draft, narration, gate, corrected, session_complete,
                          combat_started=combat_started)


class MockSetup:
    """Stand-in for Setup: a scripted new-campaign conversation that reports done after
    a few exchanges, so the TUI setup path runs offline. Speaks the same on_stage
    protocol as the real Setup so the ticker is exercised too."""

    def __init__(self, *args, **kwargs):
        self.dm_sid = "mock-setup"
        self._n = 0
        self.on_stage = None  # the TUI assigns this, same as on the real Setup

    def _announce(self, key: str) -> None:
        if self.on_stage:
            self.on_stage(key)

    def start(self) -> SetupTurn:
        self._announce("intake")
        return SetupTurn(_SETUP_SCRIPT[0], False)

    def turn(self, player_input: str) -> SetupTurn:
        self._n += 1
        i = min(self._n, len(_SETUP_SCRIPT) - 1)
        done = self._n >= len(_SETUP_SCRIPT) - 1
        if self._n == 2:
            self._announce("char")
        if done:
            for key in ("arc-major", "arc-minor", "state", "gate", "commit"):
                self._announce(key)
                time.sleep(0.4)  # let the ticker breathe, like the mock wrap
        return SetupTurn(_SETUP_SCRIPT[i], done)

    def finalize(self) -> int:
        return 1


class _NoTap:
    def stop(self) -> None:
        pass


class MockLifecycle:
    """Stand-in for Lifecycle: a MockGame plus a simulated wrap() (and an optional
    setup phase) so the TUI's full flow can be driven offline."""

    def __init__(self, start_in_setup: bool = False, *args, pace: float = 1.0, **kwargs):
        self._session = 1
        self.backend = _MockBackend()
        self.pace = pace  # see MockGame — 0 for tests, 1 for the watchable demo
        if start_in_setup:
            self.phase = "setup"
            self.game = None
            self.setup = MockSetup()
        else:
            self.phase = "play"
            self.game = MockGame(self.backend, pace=pace)
            self.setup = None

    @property
    def session(self) -> int:
        return self._session

    def status(self) -> CampaignStatus:
        """A canned snapshot so the TUI's status modal renders offline."""
        n = None if self.phase == "setup" else self._session
        return CampaignStatus(
            root=Path("/mock/campaign"), phase=self.phase, session=n,
            artifacts=[] if n is None else [
                ("plan", True), ("transcript", True), ("notes", False),
                ("digest", False)],
            reconcile_stages=[] if (n is None or n < 2) else ["digest", "assess"],
            entities_total=12, entities_complete=11,
            incomplete=["campaign/world/npcs/magren-soley.md"],
            git_state="clean", last_commit=f"session {n or 1} plan",
        )

    def player_source(self):
        """The mock is a UI harness — the player is always the keyboard (`--player auto`
        needs a real backend to prompt, and refuses the mock at the CLI)."""
        from .play import KeyboardPlayer
        return KeyboardPlayer()

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
        time.sleep(0.6 * self.pace)
        self.phase = "play"
        self.game = MockGame(self.backend, pace=self.pace)
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
            time.sleep(0.6 * self.pace)  # let the ticker breathe so the flow is visible
        self._session += 1
        self.game = MockGame(self.backend, pace=self.pace)
        return self._session
