#!/usr/bin/env python3
"""Standalone check for the SESSION LOOP (design/frontends.md step 2 — `play_session` and the
`PlayerSource` contract). No pytest, no opencode, no model — run me directly.

This is the loop every frontend now plays through, so what it asserts is the contract the
console harness, `bench run` and the TUI all depend on:

  - an `AgentPlayer` primes its FIRST message with the character packet (and the story so
    far), and nothing after it;
  - the hooks fire in order, with the turn numbers the frontends render;
  - the runner's `task_complete` ends the loop as "complete"; the cap ends it as "cap";
  - a `KeyboardPlayer` fed from another thread drives the same loop, and `stop()` ends it
    as "stopped" without touching the model;
  - a turn that calls `start_encounter` hands off to `play_combat` on the next pass — and so
    does a session *resumed* into a live fight, which is the case the old per-interface loops
    got wrong (they sent a normal turn into a live tracker);
  - a cancelled turn is handed to `on_interrupt`, costs no turn against the cap, and leaves
    the loop playing; with no hook it propagates to the caller intact (what the unattended
    callers need to record a rate-limit give-up).
"""

import copy
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import (  # noqa: E402
    AgentPlayer, Game, KeyboardPlayer, PlayHooks, play_session,
)
from gm_llm.orchestrator.backend import BackendCancelled, BackendError  # noqa: E402
from gm_llm.orchestrator.combat import CombatState  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    rolls = ()

    def __init__(self, text, tools=()):
        self.text = text
        self.tools = set(tools)
        self.tool_inputs = {}


class FakeBackend:
    """Scripted DM drafts (`prompt_full`) and player replies (`prompt`), recorded so the
    priming and the prompt stream can be asserted. A draft entry is
    `(text, tools, mutate)`; `mutate(directory)` stands in for the tracker tool calls (and
    may raise, standing in for a cancelled draft)."""

    def __init__(self, directory, drafts, players=()):
        self.directory = str(directory)
        self.drafts = list(drafts)
        self.players = list(players) or ["I look around."]
        self.i = 0                 # drafts consumed
        self.player_msgs = []      # every message the player agent was sent

    def create_session(self, title=None):
        return f"sid-{title}"

    def prompt_full(self, sid, agent, message, whole=False):
        text, tools, mutate = self.drafts[self.i]
        self.i += 1
        if mutate:
            mutate(self.directory)  # may raise, before any state change
        return _Reply(text, tools)

    def prompt(self, sid, agent, message, whole=False):
        self.player_msgs.append(message)
        i = min(len(self.player_msgs) - 1, len(self.players) - 1)
        return self.players[i]

    def context_usage(self, sid):
        return None


def _game(backend):
    return Game(backend, campaign_dir=backend.directory, session=1, transcript=False)


def _beat(text, tools=(), mutate=None):
    return (text, tools, mutate)


# ── tracker fakes (a fight the loop can drive) ───────────────────────────────

def _initial_state():
    frame = {
        "turn": "pc", "round": 1,
        "combatants": {
            "pc": {"id": "pc", "name": "Dallid", "hp": 30, "hp_max": 30, "dead": False,
                   "conditions": [], "reaction": True, "x": 0, "y": 0, "z": 0},
            "goblin-1": {"id": "goblin-1", "name": "goblin", "hp": 12, "hp_max": 12,
                         "dead": False, "conditions": [], "reaction": True,
                         "x": 30, "y": 0, "z": 0},
        },
        "initiative": ["pc", "goblin-1"], "timers": [],
    }
    return {"encounter": "goblin ambush", "next_timer_id": 1,
            "committed": copy.deepcopy(frame), "pending": copy.deepcopy(frame)}


def m_start(directory):
    CombatState(directory).save(_initial_state())


def m_act(cid, amt):
    def _mut(directory):
        st = CombatState(directory)
        s = st.load()
        s["pending"]["combatants"][cid]["hp"] -= amt
        init = s["pending"]["initiative"]
        ni = (init.index(s["pending"]["turn"]) + 1) % len(init)
        if ni == 0:
            s["pending"]["round"] += 1
        s["pending"]["turn"] = init[ni]
        st.save(s)
    return _mut


def m_end(directory):
    CombatState(directory).delete()


def m_cancel(directory):
    raise BackendCancelled("cancelled mid-draft")


def m_giveup(directory):
    raise BackendError("rate limited after 4 retries")


# ── assertion helper ──────────────────────────────────────────────────────────

def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def _recorder():
    """A PlayHooks that records every event as a flat trace, in order."""
    trace = []
    hooks = PlayHooks(
        on_prompt=lambda t: trace.append(("prompt", t)),
        on_player=lambda text, t: trace.append(("player", text, t)),
        on_turn=lambda tr: trace.append(("turn", tr.final)),
        on_slot=lambda ev, t: trace.append(("slot", ev.round, t)),
        on_beat=lambda n, who: trace.append(("beat", who)),
        on_combat_end=lambda n: trace.append(("combat_end", n)))
    return hooks, trace


# ── scenarios ─────────────────────────────────────────────────────────────────

def agent_plays_to_the_wrap():
    """An agent player runs the session to the runner's own close: the packet primes only the
    first message, the hooks fire in order, and the outcome is `complete`."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [
        _beat("The tavern is warm."),
        _beat("You bind your wounds and rest.", {"task_complete"}),
    ], players=["I look around.", "I call it a night."])
    game = _game(backend)
    hooks, trace = _recorder()

    source = AgentPlayer(backend, "sid-player", character="You are Dallid, a cleric.",
                         story="Rain. A locked door.")
    result = play_session(game, source, "You push open the tavern door.", hooks=hooks,
                          turn_cap=10)

    check(result.outcome == "complete", f"the runner's task_complete ends it — {result.outcome}")
    check(result.turns == 2, f"two player turns played — got {result.turns}")
    check(result.scene.startswith("You bind"), "the final narration comes back as the scene")
    check(trace == [
        ("prompt", 1), ("player", "I look around.", 1), ("turn", "The tavern is warm."),
        ("prompt", 2), ("player", "I call it a night.", 2),
        ("turn", "You bind your wounds and rest."),
    ], f"hooks fire in order, with the turn numbers a frontend renders — got {trace}")

    first, second = backend.player_msgs
    check("You are Dallid, a cleric." in first and "Rain. A locked door." in first,
          "the first message carries the packet and the story so far")
    check(first.endswith("<dm>\nYou push open the tavern door.\n</dm>"),
          "…in front of the ordinary per-turn body, which closes the message")
    check("You are Dallid" not in second and "Rain." not in second,
          "priming is first-message-only — every later turn is the reminder alone")
    check(second.endswith("<dm>\nThe tavern is warm.\n</dm>"),
          "each turn responds to the scene the last one produced")
    print("agent_plays_to_the_wrap: priming, hook order and the wrap signal all correct.\n")


def the_cap_is_the_only_other_ending():
    """No wrap in sight: the cap stops the loop at exactly `turn_cap` turns."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [_beat(f"Beat {i}.") for i in range(1, 6)])
    game = _game(backend)
    hooks, trace = _recorder()

    result = play_session(game, AgentPlayer(backend, "sid-player"), "The scene.", hooks=hooks,
                          turns=1, turn_cap=3)

    check(result.outcome == "cap", f"outcome is a cap breach — got {result.outcome}")
    check(result.turns == 3, f"the count includes the turns already on disk — got {result.turns}")
    check(backend.i == 2, f"two drafts for the two turns left under the cap — got {backend.i}")
    check([t for t in trace if t[0] == "prompt"] == [("prompt", 2), ("prompt", 3)],
          f"numbering continues past the turns handed in — got {trace}")
    print("the_cap_is_the_only_other_ending: the cap counts from where the caller left off.\n")


def keyboard_player_drives_the_same_loop():
    """The human end: a `KeyboardPlayer` fed from another thread plays the same loop, and
    `stop()` ends it as `stopped` — no model call, nothing about the session settled."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [_beat("Magren slides a mug across the bar.")])
    game = _game(backend)
    hooks, trace = _recorder()
    source = KeyboardPlayer()
    box = {}

    def run():
        box["result"] = play_session(game, source, "The inn is loud.", hooks=hooks)

    worker = threading.Thread(target=run)
    worker.start()
    _wait(lambda: ("prompt", 1) in trace, "the loop asks the keyboard for turn 1")
    source.submit("I ask about the satchel.")
    _wait(lambda: any(t[0] == "turn" for t in trace), "the typed line plays a turn")
    _wait(lambda: ("prompt", 2) in trace, "and the loop comes back for the next one")
    source.stop()
    worker.join(timeout=5)

    check(not worker.is_alive(), "stop() releases the parked thread")
    result = box["result"]
    check(result.outcome == "stopped", f"a stopped source is not an ending — {result.outcome}")
    check(result.turns == 1, f"the one played turn is reported — got {result.turns}")
    check(backend.i == 1, "the un-asked turn cost no model call")
    check(("player", "I ask about the satchel.", 1) in trace, "the typed line rode the hook")
    print("keyboard_player_drives_the_same_loop: one loop, human on the other end.\n")


def stopping_an_agent_player_is_graceful():
    """A frontend wrapping a watched run calls `stop()` on whatever source it has. For an
    agent player that lands at the next ask, so the turn in flight is finished and kept —
    never thrown away half-played."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [_beat("Magren nods."), _beat("Never asked for.")])
    game = _game(backend)
    hooks, trace = _recorder()
    source = AgentPlayer(backend, "sid-player")
    hooks.on_turn = lambda tr: (trace.append(("turn", tr.final)), source.stop())

    result = play_session(game, source, "The inn is loud.", hooks=hooks, turn_cap=10)

    check(result.outcome == "stopped", f"the stop ends the loop — got {result.outcome}")
    check(result.turns == 1, f"the turn in flight was finished and counted — {result.turns}")
    check(result.scene == "Magren nods.", "…and its narration is the scene handed back")
    check(backend.i == 1, "no further draft — the stop landed at the next ask")
    print("stopping_an_agent_player_is_graceful: a wrap never eats a turn in flight.\n")


def a_fight_is_entered_from_the_top_of_the_loop():
    """A turn that calls `start_encounter` hands the next pass to `play_combat`; each PC slot
    burns a turn, and normal play resumes from the exit beat."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [
        _beat("Steel rings free — roll initiative!", {"start_encounter"}, m_start),
        _beat("You lunge; your blade bites deep.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        _beat("The goblin breaks and flees.", {"end_encounter"}, m_end),
        _beat("You bind your wounds and rest.", {"task_complete"}),
    ])
    game = _game(backend)
    hooks, trace = _recorder()

    result = play_session(game, AgentPlayer(backend, "sid-player"), "The door bangs open.",
                          hooks=hooks, turn_cap=10)

    check(result.outcome == "complete", f"play resumed and wrapped — got {result.outcome}")
    check(result.turns == 3, f"1 entry turn + 1 PC slot + 1 wrap turn — got {result.turns}")
    check([t[0] for t in trace] == [
        "prompt", "player", "turn",              # the turn that starts the fight
        "slot", "player", "beat", "combat_end",  # the PC slot, its beat, the fight's end
        "prompt", "player", "turn",              # normal play resumes
    ], f"the fight is entered from the loop's next pass — got {[t[0] for t in trace]}")
    check(("slot", 1, 2) in trace, f"the PC slot is turn 2, round 1 — got {trace}")
    check("<dm>\nThe goblin breaks and flees.\n</dm>" in backend.player_msgs[-1],
          "normal play resumes from the fight's exit beat")
    print("a_fight_is_entered_from_the_top_of_the_loop: entry, accounting, and resumption.\n")


def a_session_resumed_into_a_live_fight_never_plays_a_normal_turn():
    """The case every per-interface loop got wrong: a `Game` whose `_in_combat` recovered off
    the tracker file must fight, not send a normal turn into a live encounter."""
    tmp = tempfile.mkdtemp()
    CombatState(tmp).save(_initial_state())
    backend = FakeBackend(tmp, [
        _beat("You strike at the goblin.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        _beat("The goblin flees into the dark.", {"end_encounter"}, m_end),
        _beat("You catch your breath.", {"task_complete"}),
    ])
    game = _game(backend)
    check(game.in_combat, "the fresh Game recovered in_combat off the state file")
    hooks, trace = _recorder()

    result = play_session(game, AgentPlayer(backend, "sid-player", character="Dallid, a cleric."),
                          "Steel is out.", hooks=hooks, turn_cap=10)

    check(result.outcome == "complete", f"the resumed fight ran on into a wrap — {result.outcome}")
    check(trace[0][0] == "slot", f"the first thing asked for is the PC's slot — got {trace[0]}")
    check("Dallid, a cleric." in backend.player_msgs[0],
          "the packet still primes the first message, even though it is a combat slot")
    print("a_session_resumed_into_a_live_fight_never_plays_a_normal_turn: combat wins.\n")


def an_interrupt_is_the_frontend_s_to_answer():
    """A cancelled turn: with a hook the loop plays on and the abandoned turn costs nothing;
    with no hook it propagates, which is how an unattended run records a give-up."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [
        _beat("", (), m_cancel),                       # turn 1 is cancelled mid-draft
        _beat("Magren looks up.", ()),                 # the retry lands
        _beat("You call it a night.", {"task_complete"}),
    ])
    game = _game(backend)
    hooks, trace = _recorder()
    seen = []
    hooks.on_interrupt = lambda stage, exc, msg: (seen.append((stage, type(exc).__name__, msg))
                                                  or True)

    result = play_session(game, AgentPlayer(backend, "sid-player"), "The inn is loud.",
                          hooks=hooks, turn_cap=2)

    check(result.outcome == "complete", f"the session survived the cancel — {result.outcome}")
    check(seen == [("turn", "BackendCancelled", "I look around.")],
          f"the hook got the stage, the exception and the message back — got {seen}")
    check(result.turns == 2, f"two turns landed; the cancelled one cost nothing — {result.turns}")
    check([t for t in trace if t[0] == "prompt"] == [("prompt", 1), ("prompt", 1), ("prompt", 2)],
          f"the abandoned turn's number is re-used, not burned — got {trace}")

    # No hook: the give-up rides out to the caller, which is what bench records a run on.
    backend2 = FakeBackend(tmp, [_beat("", (), m_giveup)])
    raised = False
    try:
        play_session(_game(backend2), AgentPlayer(backend2, "sid-player"), "The inn is loud.",
                     hooks=PlayHooks(), turn_cap=5)
    except BackendError:
        raised = True
    check(raised, "with no on_interrupt, a backend give-up propagates untouched")
    print("an_interrupt_is_the_frontend_s_to_answer: continue or propagate, never silent.\n")


def _wait(cond, what, timeout=5.0):
    """Poll until `cond()` — the threaded scenarios have no clock to fix, only an order."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            print(f"  ok: {what}")
            return
        time.sleep(0.01)
    print(f"FAIL: timed out waiting for {what}")
    sys.exit(1)


if __name__ == "__main__":
    agent_plays_to_the_wrap()
    the_cap_is_the_only_other_ending()
    keyboard_player_drives_the_same_loop()
    stopping_an_agent_player_is_graceful()
    a_fight_is_entered_from_the_top_of_the_loop()
    a_session_resumed_into_a_live_fight_never_plays_a_normal_turn()
    an_interrupt_is_the_frontend_s_to_answer()
    print("OK — session loop: priming, hooks, cap, keyboard, combat handoff, interrupts.")
