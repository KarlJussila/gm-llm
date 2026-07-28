#!/usr/bin/env python3
"""Standalone check for the combat DRIVER (design/combat.md — the sequencing policy that wraps
`Game`'s initiative surface). No pytest, no opencode, no model — run me directly.

Drives the real `CombatDriver` over the same fake tracker backend `dev/test_combat_loop.py`
uses (a fake whose scripted replies mutate the tracker state file the way the plugin's
tool calls would). The driver is where the *loop* policy lives — pump NPC beats, confirm
each, stop at a PC slot or the fight's end, thread interjections and cancels — so this
asserts that policy end to end, over the callback contract the three interfaces drive it
through:

  - the NPC pump renders each beat via `on_beat` and auto-confirms;
  - a PC slot is handed back (kind="pc_slot") for the interface to solicit input;
  - `pc_action` plays the slot and resumes pumping;
  - an `on_beat` that returns a reaction interjects (rollback + replay + re-present);
  - the fight's end is handed back (kind="ended") with the exit narration;
  - a `BackendCancelled` mid-beat propagates out with the tracker left consistent;
  - a resume into a live fight (a fresh Game whose _in_combat recovered off the state
    file) is driven straight through `advance`.
"""

import copy
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import CombatDriver, Game  # noqa: E402
from gm_llm.orchestrator.backend import BackendCancelled  # noqa: E402
from gm_llm.orchestrator.combat import CombatState  # noqa: E402
from gm_llm.orchestrator.gate import GateResult, Verdict  # noqa: E402


# ── fakes (mirrors test_combat_loop) ─────────────────────────────────────────

class _Reply:
    def __init__(self, text, tools=()):
        self.text = text
        self.tools = set(tools)
        self.tool_inputs = {}


def _initial_state():
    def c(cid, name, hp, x, y):
        return {"id": cid, "name": name, "hp": hp, "hp_max": hp, "dead": False,
                "conditions": [], "reaction": True, "x": x, "y": y, "z": 0}
    frame = {
        "turn": "pc", "round": 1,
        "combatants": {
            "pc": {"id": "pc", "name": "Dallid", "hp": 30, "hp_max": 30, "dead": False,
                   "conditions": [], "reaction": True, "x": 0, "y": 0, "z": 0},
            "goblin-1": c("goblin-1", "goblin", 12, 30, 0),
            "goblin-2": c("goblin-2", "goblin", 12, 0, 30),
        },
        "initiative": ["pc", "goblin-1", "goblin-2"],
        "timers": [],
    }
    return {"encounter": "goblin ambush", "next_timer_id": 1,
            "committed": copy.deepcopy(frame), "pending": copy.deepcopy(frame)}


class FakeBackend:
    def __init__(self, directory, script):
        self.directory = str(directory)
        self.script = list(script)
        self.i = 0

    def create_session(self, title):
        return f"sid-{title}"

    def _next(self):
        text, tools, mutate = self.script[self.i]
        self.i += 1
        if mutate:
            mutate(self.directory)  # may raise (a cancelled draft) before any state change
        return _Reply(text, tools)

    def prompt_full(self, sid, agent, message, whole=False):
        return self._next()

    def prompt(self, sid, agent, message, whole=False):
        return self._next().text

    def context_usage(self, sid):
        return None


class FakeGate:
    def check(self, narration, player_msg, in_combat=False):
        combat = Verdict("check-combat", True, "") if in_combat else None
        return GateResult(Verdict("check-turn", True, ""), Verdict("check-conduct", True, ""),
                          player_msg, canon_sections=0, combat=combat)


# ── state-file mutations ──────────────────────────────────────────────────────

def m_start(directory):
    CombatState(directory).save(_initial_state())


def _advance_pending(s):
    init = s["pending"]["initiative"]
    ni = (init.index(s["pending"]["turn"]) + 1) % len(init)
    if ni == 0:
        s["pending"]["round"] += 1
    s["pending"]["turn"] = init[ni]


def m_act(cid, amt):
    def _mut(directory):
        st = CombatState(directory)
        s = st.load()
        c = s["pending"]["combatants"][cid]
        c["hp"] = max(0, c["hp"] - amt)
        _advance_pending(s)
        st.save(s)
    return _mut


def m_end(directory):
    CombatState(directory).delete()


def m_cancel(directory):
    raise BackendCancelled("cancelled mid-draft")  # before any state mutation


# ── assertion helpers ─────────────────────────────────────────────────────────

def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def _enter(game, backend):
    """Play the entry turn (start_encounter) and hand back a driver over the fight."""
    tr = game.turn("I ready my blade.")
    check(tr.combat_started, "entry turn reports combat_started")
    check(game.in_combat, "in_combat True after start_encounter")
    return CombatDriver(game)


# ── scenarios ─────────────────────────────────────────────────────────────────

def pump_and_end():
    """NPC pump + PC slot handoff + combat end back to normal play."""
    tmp = tempfile.mkdtemp()
    script = [
        ("Blades out — initiative!", {"start_encounter"}, m_start),
        ("You lunge; your blade bites deep.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        ("The goblin's blade rakes your side.", {"damage", "advance_turn"}, m_act("pc", 6)),
        ("The last goblin breaks and flees into the dark.", {"end_encounter"}, m_end),
    ]
    backend = FakeBackend(tmp, script)
    game = Game(backend, FakeGate(), campaign_dir=tmp, session=1, transcript=False)
    driver = _enter(game, backend)
    beats = []

    def on_beat(narration, who):
        beats.append((narration, who))
        return None  # never interject

    event = driver.advance(on_beat)
    check(event.kind == "pc_slot", "advance stops at the PC's slot")
    check(event.combatant == "pc" and event.round == 1, "the pc_slot event names pc / round 1")
    check(beats == [], "no beats rendered before the PC has acted")

    event = driver.pc_action("I attack the nearer goblin.", on_beat)
    check(event.kind == "ended", "the fight ends after the NPC pump")
    check(event.narration.startswith("The last goblin"), "the exit narration rides on the event")
    check([w for _, w in beats] == ["pc", "goblin-1"],
          "on_beat rendered the PC beat then the one NPC beat (the exit beat rides the event)")
    check(not game.in_combat, "in_combat flips back to False on end")
    check(not CombatState(tmp).exists(), "the tracker state file is gone after the fight")
    check(backend.i == len(script), "every scripted call consumed, in order")
    print("pump_and_end: NPC pump, PC slot, and clean exit all correct.\n")


def interject_via_callback():
    """on_beat returning a reaction interjects (rollback + replay + re-present)."""
    tmp = tempfile.mkdtemp()
    script = [
        ("Blades out — initiative!", {"start_encounter"}, m_start),
        ("You lunge; your blade bites deep.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        ("The goblin's blade rakes your side.", {"damage", "advance_turn"}, m_act("pc", 6)),
        ("Your shield flares; the blow glances off.", {"damage", "advance_turn"}, m_act("pc", 2)),
        ("The last goblin turns and flees.", {"end_encounter"}, m_end),
    ]
    backend = FakeBackend(tmp, script)
    game = Game(backend, FakeGate(), campaign_dir=tmp, session=1, transcript=False)
    driver = _enter(game, backend)
    st = CombatState(tmp)
    beats, reacted = [], {"done": False}

    def on_beat(narration, who):
        beats.append((narration, who))
        if who == "goblin-1" and not reacted["done"]:
            reacted["done"] = True
            return "I cast shield!"  # interject once, on the first goblin-1 beat
        return None

    driver.advance(on_beat)  # PC slot
    event = driver.pc_action("I attack the nearer goblin.", on_beat)
    check(event.kind == "ended", "the fight ends after the interject is confirmed")
    check([n for n, _ in beats] == [
        "You lunge; your blade bites deep.",
        "The goblin's blade rakes your side.",
        "Your shield flares; the blow glances off."],
        "on_beat saw the PC beat, the goblin hit, then the replayed (blunted) beat")
    check(not st.exists(), "state file gone after the fight")
    check(backend.i == len(script), "the interject's replay call was consumed")
    print("interject_via_callback: rollback + replay + re-present via the on_beat return.\n")


def cancel_unwind():
    """A BackendCancelled mid-beat propagates out, tracker left consistent."""
    tmp = tempfile.mkdtemp()
    script = [
        ("Blades out — initiative!", {"start_encounter"}, m_start),
        ("You lunge; your blade bites deep.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        ("", (), m_cancel),  # goblin-1's draft is cancelled mid-flight
    ]
    backend = FakeBackend(tmp, script)
    game = Game(backend, FakeGate(), campaign_dir=tmp, session=1, transcript=False)
    driver = _enter(game, backend)
    st = CombatState(tmp)

    driver.advance(lambda n, w: None)  # -> PC slot
    raised = False
    try:
        driver.pc_action("I attack.", lambda n, w: None)  # commits PC, then cancels on goblin-1
    except BackendCancelled:
        raised = True
    check(raised, "BackendCancelled propagates out of the driver")
    check(game.in_combat and st.exists(), "still in combat — the fight isn't lost to the cancel")
    check(not st.in_flight(), "no half-applied action survives (committed == pending)")
    check(st.load()["committed"]["combatants"]["pc"]["hp"] == 30,
          "the cancelled goblin-1 draft left the PC unhurt")
    check(st.turn == "goblin-1", "the turn pointer rests on the interrupted combatant")
    print("cancel_unwind: cancel raises cleanly, tracker state stays consistent.\n")


def resume_into_combat():
    """A fresh Game resumed into a live fight is driven straight through advance()."""
    tmp = tempfile.mkdtemp()
    # Persisted crash state: goblin-1's action in flight (pending advanced, uncommitted).
    s = _initial_state()
    for frame in ("committed", "pending"):
        s[frame]["turn"] = "goblin-1"
    s["pending"]["combatants"]["pc"]["hp"] = 24
    _advance_pending(s)
    CombatState(tmp).save(s)

    script = [
        ("The goblin's blade rakes your side.", {"damage", "advance_turn"}, m_act("pc", 6)),
        ("The last goblin flees into the dark.", {"end_encounter"}, m_end),
    ]
    backend = FakeBackend(tmp, script)
    game = Game(backend, FakeGate(), campaign_dir=tmp, session=1, transcript=False)
    check(game.in_combat, "a fresh Game recovers in_combat off the state file")
    driver = CombatDriver(game)
    check(driver.in_combat, "the driver mirrors the game's combat state")
    beats = []

    event = driver.advance(lambda n, w: beats.append(w))
    check(event.kind == "ended", "the resumed fight drives to its end through advance()")
    check(beats == ["goblin-1"], "the interrupted combatant is re-resolved, then the fight ends")
    check(not game.in_combat, "in_combat False after the resumed fight ends")
    check(backend.i == len(script), "exactly the re-resolution + exit calls consumed")
    print("resume_into_combat: a crash-recovered fight drives cleanly through the driver.\n")


if __name__ == "__main__":
    pump_and_end()
    interject_via_callback()
    cancel_unwind()
    resume_into_combat()
    print("OK — combat driver: pump, PC slot, interject, cancel, resume all correct.")
