#!/usr/bin/env python3
"""Standalone check for the TUI's side of the session loop — no pytest; run me directly.

Drives the real `PlayApp` headlessly (Textual's own `run_test` pilot) over `MockLifecycle`,
so this is the app's actual event loop, workers, threads and key handling — only the model
is fake. It exists because frontends 2 moved the TUI from a worker per turn to one
`play_session` worker per session, with the keyboard as a `PlayerSource`: everything that
used to be straight-line code in `_do_turn` is now a hand-off between two threads, and
nothing else in the suite would notice if a hand-off stopped arriving.

What it pins, end to end through the keyboard:

  - the opening scene, then a typed turn: the line is echoed once (by the loop's `on_player`,
    not by the input handler) and the DM's beat lands;
  - a turn that starts a fight enters combat *from the loop*, and the confirm gate takes a
    bare Enter for confirm and a typed line for a reaction;
  - the fight's exit beat is rendered and normal turns resume;
  - the runner's `task_complete` offers the wrap, the wrap runs, and the next session opens
    on a fresh loop;
  - ctrl+x cancels the turn in flight, hands the message back to the box, and leaves the
    loop playing (the interrupt hook's whole point).

The mock's scripted delays are scenery, so it runs at `pace=0` — except the cancel scenario,
which needs a call actually in flight to cancel.
"""

import asyncio
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from textual.widgets import Input  # noqa: E402

from gm_llm.orchestrator.mock import MockLifecycle  # noqa: E402
from gm_llm.tui.app import PlayApp  # noqa: E402
from gm_llm.tui.widgets import DMBlock, PlayerLine  # noqa: E402


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


async def until(pilot, cond, what, timeout=15.0):
    """Wait for a condition instead of for a clock — the app is threaded, so the only thing
    a test may rely on is the order of what it observes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            await pilot.pause()
            print(f"  ok: {what}")
            return
        await pilot.pause()
        await asyncio.sleep(0.01)
    print(f"FAIL: timed out waiting for {what}")
    sys.exit(1)


async def submit(pilot, text=""):
    """Type a line into the play bar and send it (the real key path, so the app's own
    routing — combat confirm, commands, drafting — is what runs)."""
    inp = pilot.app.query_one("#cmd", Input)
    inp.focus()
    inp.value = text
    await pilot.press("enter")
    await pilot.pause()


def dm_beats(app):
    return len(app.query(DMBlock))


def player_lines(app):
    return len(app.query(PlayerLine))


# ── scenarios ─────────────────────────────────────────────────────────────────

async def a_whole_session_through_the_keyboard():
    app = PlayApp(MockLifecycle(pace=0.0))
    async with app.run_test() as pilot:
        await until(pilot, lambda: dm_beats(app) >= 1, "the opening scene lands")
        check(app._loop_live, "the session loop is running behind it")
        check(app._source.human, "the keyboard is the player source")

        # -- turn 1: a plain typed turn --------------------------------------
        await submit(pilot, "I look around the common room.")
        await until(pilot, lambda: dm_beats(app) == 2, "the typed turn plays a DM beat")
        check(player_lines(app) == 1, f"the line is echoed exactly once — {player_lines(app)}")

        # -- turn 2: the mock starts a fight ---------------------------------
        await submit(pilot, "I draw my blade.")
        await until(pilot, lambda: app._combat_awaiting == "pc",
                    "the fight is entered and stops at the PC's slot")
        check(app.game.in_combat, "the game is in combat")

        await submit(pilot, "I strike the nearer thug.")
        await until(pilot, lambda: app._combat_awaiting == "confirm",
                    "the PC beat resolves and an NPC beat awaits confirm")

        # a typed line at the confirm gate is a reaction, not a turn
        beats_before = dm_beats(app)
        await submit(pilot, "I raise my shield!")
        await until(pilot, lambda: dm_beats(app) > beats_before and
                    app._combat_awaiting == "confirm", "a reaction replays the beat, re-armed")

        await submit(pilot)  # bare Enter confirms
        await until(pilot, lambda: app._combat_awaiting == "confirm",
                    "the next NPC beat comes up for confirm")
        await submit(pilot)
        await until(pilot, lambda: not app.game.in_combat and app._combat_awaiting is None,
                    "the fight ends and the loop returns to normal turns")

        # -- turns 3-6: the mock wraps the session on its sixth turn ----------
        for i in range(3, 7):
            beats = dm_beats(app)
            await submit(pilot, f"I keep going ({i}).")
            await until(pilot, lambda beats=beats: dm_beats(app) > beats, f"turn {i} plays")

        await until(pilot, lambda: app._pending == "wrap",
                    "the runner's close offers the wrap instead of running it")
        check(not app._loop_live, "the session loop ended with the session")

        # -- the wrap, then the next session on a fresh loop -----------------
        # `ask()` takes focus, so the phase prompt answers to a bare y (see PromptBar).
        await pilot.press("y")
        await until(pilot, lambda: app._pending == "open" and not app._wrapping,
                    "the pipeline runs and session 2 is planned")
        await pilot.press("y")
        await until(pilot, lambda: app._loop_live and app.lc.session == 2,
                    "session 2 opens on a new loop")
        check(app._source is not None and app._source.human,
              "with a fresh source — a stopped one would never wake")
        app.exit()
    print("a_whole_session_through_the_keyboard: play, fight, wrap, next session.\n")


async def cancel_hands_the_message_back_and_plays_on():
    app = PlayApp(MockLifecycle(pace=1.0))  # a real delay, so there is a call to cancel
    async with app.run_test() as pilot:
        await until(pilot, lambda: dm_beats(app) >= 1, "the opening scene lands")
        await submit(pilot, "I mistype something.")
        await until(pilot, lambda: app._working, "the turn is in flight")
        await pilot.press("ctrl+x")
        await until(pilot, lambda: not app._working,
                    "the cancel unwinds the turn instead of waiting it out")
        check(app.query_one("#cmd", Input).value == "I mistype something.",
              "the cancelled message is back in the box")
        check(app._loop_live, "the session loop survived the cancel")

        await submit(pilot, "I try again.")
        await until(pilot, lambda: dm_beats(app) == 2, "and the next turn plays normally")
        app.exit()
    print("cancel_hands_the_message_back_and_plays_on: an interrupt is not an ending.\n")


if __name__ == "__main__":
    asyncio.run(a_whole_session_through_the_keyboard())
    asyncio.run(cancel_hands_the_message_back_and_plays_on())
    print("OK — TUI: one session loop, keyboard source, combat gate, wrap, cancel.")
