#!/usr/bin/env python3
"""Standalone check for the TUI as a client of the engine — no pytest; run me directly.

Drives the real `PlayApp` headlessly (Textual's own `run_test` pilot) over an `Engine` on
`MockLifecycle` — so this is the app's actual event pump, key handling and rendering, and
the engine's actual threads; only the model is fake.

What it pins, end to end through the keyboard:

  - the opening scene, then a typed turn: the line is echoed once (by the engine's `say`)
    and the DM's beat lands;
  - a fight: the PC's slot takes a typed action, the confirm gate a bare Enter or a
    reaction, and normal turns resume;
  - the runner's close offers the wrap on the prompt bar, `y` runs it, and `y` again opens
    the next session;
  - ctrl+x cancels the turn in flight and the message comes back to the box;
  - the frontends import nothing of the orchestrator's or the bench's.

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

from gm_llm.engine.client import LocalClient  # noqa: E402
from gm_llm.engine.core import Engine  # noqa: E402
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


def _app(pace=0.0):
    return PlayApp(LocalClient(Engine(MockLifecycle(pace=pace))))


def awaiting(app):
    return app.state.get("awaiting")


# ── scenarios ─────────────────────────────────────────────────────────────────

async def a_whole_session_through_the_keyboard():
    app = _app()
    async with app.run_test() as pilot:
        await until(pilot, lambda: dm_beats(app) >= 1 and awaiting(app) == "turn",
                    "the opening scene lands and the engine asks for a turn")

        # -- turn 1: a plain typed turn --------------------------------------
        await submit(pilot, "I look around the common room.")
        await until(pilot, lambda: dm_beats(app) == 2, "the typed turn plays a DM beat")
        check(player_lines(app) == 1, f"the line is echoed exactly once — {player_lines(app)}")

        # -- turn 2: the mock starts a fight ---------------------------------
        await submit(pilot, "I draw my blade.")
        await until(pilot, lambda: awaiting(app) == "pc_action",
                    "the fight is entered and stops at the PC's slot")
        check(app.state["in_combat"], "the state says the fight is on")

        await submit(pilot, "I strike the nearer thug.")
        await until(pilot, lambda: awaiting(app) == "confirm",
                    "the PC beat resolves and an NPC beat awaits confirm")

        # a typed line at the confirm gate is a reaction, not a turn
        beats_before = dm_beats(app)
        await submit(pilot, "I raise my shield!")
        await until(pilot, lambda: dm_beats(app) > beats_before and awaiting(app) == "confirm",
                    "a reaction replays the beat, re-armed")

        await submit(pilot)  # bare Enter confirms
        await until(pilot, lambda: awaiting(app) == "confirm",
                    "the next NPC beat comes up for confirm")
        await submit(pilot)
        await until(pilot, lambda: not app.state["in_combat"] and awaiting(app) == "turn",
                    "the fight ends and normal turns resume")

        # -- turns 3-6: the mock wraps the session on its sixth turn ----------
        for i in range(3, 7):
            beats = dm_beats(app)
            await submit(pilot, f"I keep going ({i}).")
            await until(pilot, lambda beats=beats: dm_beats(app) > beats, f"turn {i} plays")

        await until(pilot, lambda: app.state["phase"] == "complete" and app._prompt.active,
                    "the runner's close offers the wrap instead of running it")

        # -- the wrap, then the next session -----------------------------------
        # `ask()` takes focus, so the phase prompt answers to a bare y (see PromptBar).
        await pilot.press("y")
        await until(pilot, lambda: app.state["phase"] == "ready" and app._prompt.active,
                    "the pipeline runs and session 2 is planned")
        await pilot.press("y")
        await until(pilot, lambda: awaiting(app) == "turn" and app.state["session"] == 2,
                    "session 2 opens and asks for a turn")
        app.exit()
    app.client.close()
    print("a_whole_session_through_the_keyboard: play, fight, wrap, next session.\n")


async def cancel_hands_the_message_back_and_plays_on():
    app = _app(pace=1.0)  # a real delay, so there is a call to cancel
    async with app.run_test() as pilot:
        await until(pilot, lambda: awaiting(app) == "turn", "the opening scene lands")
        await submit(pilot, "I mistype something.")
        await until(pilot, lambda: "cancel" in app.state["actions"], "the turn is in flight")
        await pilot.press("ctrl+x")
        await until(pilot, lambda: awaiting(app) == "turn",
                    "the cancel unwinds the turn instead of waiting it out")
        check(app.query_one("#cmd", Input).value == "I mistype something.",
              "the cancelled message is back in the box")

        await submit(pilot, "I try again.")
        await until(pilot, lambda: dm_beats(app) == 2, "and the next turn plays normally")
        app.exit()
    app.client.close()
    print("cancel_hands_the_message_back_and_plays_on: an interrupt is not an ending.\n")


def the_frontends_import_no_workflow():
    import subprocess
    probe = ("import sys, gm_llm.tui.app, gm_llm.consoleui, gm_llm.engine.client; "
             "print(' '.join(m for m in sys.modules if m.startswith("
             "('gm_llm.orchestrator', 'gm_llm.bench', 'gm_llm.engine.core'))))")
    out = subprocess.run([sys.executable, "-c", probe], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout.strip()
    check(out == "", f"the TUI and console import only the engine client — got: {out}")
    print()


if __name__ == "__main__":
    asyncio.run(a_whole_session_through_the_keyboard())
    asyncio.run(cancel_hands_the_message_back_and_plays_on())
    the_frontends_import_no_workflow()
    print("OK — TUI over the engine: turns, combat gate, wrap, cancel, the import boundary.")
