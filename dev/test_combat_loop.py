#!/usr/bin/env python3
"""Standalone check for the combat mode-switch loop (COMBAT.md C1) — no pytest, no
opencode, no model. Run me directly.

Drives the real `Game` combat surface over a fake backend that simulates the tracker
plugin's effect on the state file (start_encounter seeds it; advance_turn moves the
top-level turn pointer; damage mutates `pending`; end_encounter deletes it). The point
is the **commit/rollback boundaries**: after each step we read the state file and assert
`committed` vs. `pending` are exactly where the invariant says they should be —

  - the PC's own turn commits directly (no confirm gate);
  - an NPC turn advances + commits at the TOP (committed == that combatant's post-advance
    start), then resolves the action into `pending` only, awaiting confirm;
  - an interject rolls `pending` back to `committed` (turn pointer intact) and replays;
  - a bare confirm hardens `pending` into `committed`;
  - end_encounter leaves combat and drops the file.

This is the C1 exit criterion in miniature: a scripted combat drives through the loop
with correct commit/rollback boundaries and no model.
"""

import copy
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import Game  # noqa: E402
from gm_llm.orchestrator.combat import CombatState  # noqa: E402
from gm_llm.orchestrator.gate import GateResult, Verdict  # noqa: E402


# ── fakes ───────────────────────────────────────────────────────────────────

class _Reply:
    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = set(tools)
        self.tool_inputs = tool_inputs or {}


def _initial_state():
    def c(cid, name, hp, x, y):
        return {"id": cid, "name": name, "hp": hp, "hp_max": hp, "dead": False,
                "conditions": [], "reaction": True, "x": x, "y": y, "z": 0}
    frame = {
        "combatants": {
            "pc": {"id": "pc", "name": "Dallid", "hp": 30, "hp_max": 30, "dead": False,
                   "conditions": [], "reaction": True, "x": 0, "y": 0, "z": 0},
            "goblin-1": c("goblin-1", "goblin", 12, 30, 0),
            "goblin-2": c("goblin-2", "goblin", 12, 0, 30),
        },
        "initiative": ["pc", "goblin-1", "goblin-2"],
        "timers": [],
    }
    return {"encounter": "goblin ambush", "round": 1, "turn": "pc", "next_timer_id": 1,
            "committed": copy.deepcopy(frame), "pending": copy.deepcopy(frame)}


class FakeBackend:
    """Scripted replies whose side effects on the tracker state file stand in for the
    plugin's tool calls. Each script entry is (text, tools, mutate)."""

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
            mutate(self.directory)
        return _Reply(text, tools)

    def prompt_full(self, sid, agent, message, whole=False):
        return self._next()

    def prompt(self, sid, agent, message, whole=False):
        return self._next().text

    def context_usage(self, sid):
        return None


class FakeGate:
    """Always-clean verdicts — C1 is about the loop's commit boundaries, not the check."""

    def check(self, narration, player_msg):
        v = Verdict("check-turn", True, "")
        return GateResult(v, Verdict("check-conduct", True, ""), player_msg, canon_sections=0)


# ── state-file mutations the fake backend applies ─────────────────────────────

def m_start(directory):
    CombatState(directory).save(_initial_state())


def m_advance(directory):
    st = CombatState(directory)
    s = st.load()
    init = s["pending"]["initiative"]
    ni = (init.index(s["turn"]) + 1) % len(init)
    if ni == 0:
        s["round"] += 1
    s["turn"] = init[ni]
    st.save(s)


def m_damage(cid, amt):
    def _mut(directory):
        st = CombatState(directory)
        s = st.load()
        c = s["pending"]["combatants"][cid]
        c["hp"] = max(0, c["hp"] - amt)
        st.save(s)
    return _mut


def m_end(directory):
    CombatState(directory).delete()


# ── assertions helpers ────────────────────────────────────────────────────────

def hp(st, frame, cid):
    return st.load()[frame]["combatants"][cid]["hp"]


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


# ── the scripted combat ───────────────────────────────────────────────────────

def main():
    tmp = tempfile.mkdtemp()
    script = [
        # 1. entry: a normal turn whose narration calls start_encounter
        ("Blades out — roll initiative!", {"start_encounter"}, m_start),
        # 2. PC's turn: strike goblin-1 for 5
        ("You lunge; your blade bites deep.", {"damage"}, m_damage("goblin-1", 5)),
        # 3. advance pc -> goblin-1
        ("", {"advance_turn"}, m_advance),
        # 4. goblin-1's turn: hit the PC for 6
        ("The goblin's blade rakes your side.", {"damage"}, m_damage("pc", 6)),
        # 5. interject replay: the shield spell blunts it to 2
        ("Your shield flares; the blow glances off.", {"damage"}, m_damage("pc", 2)),
        # 6. advance goblin-1 -> goblin-2
        ("", {"advance_turn"}, m_advance),
        # 7. goblin-2's turn: it breaks and the fight ends
        ("The last goblin turns and flees into the dark.", {"end_encounter"}, m_end),
    ]
    backend = FakeBackend(tmp, script)
    game = Game(backend, FakeGate(), campaign_dir=tmp, session=1, transcript=False)
    st = CombatState(tmp)

    check(not game.in_combat, "not in combat before start_encounter")

    # --- enter combat via a normal player-driven turn -------------------------
    tr = game.turn("I ready my blade.")
    check(tr.combat_started, "turn() reports combat_started on start_encounter")
    check(game.in_combat, "in_combat flips True after start_encounter")

    # --- combat_step 1: the PC is up (first step never advances) --------------
    step = game.combat_step()
    check(step.kind == "await_pc", "first combat_step yields the PC's turn")
    check(st.turn == "pc", "first step did NOT advance (start_encounter seated the PC)")

    # --- PC acts: commits directly, no advance --------------------------------
    step = game.combat_player_action("I attack the nearer goblin.")
    check(step.kind == "committed", "PC action commits directly (no confirm gate)")
    check(st.turn == "pc", "PC action does not advance the turn")
    check(hp(st, "committed", "goblin-1") == 7, "PC's 5 damage hardened into committed")
    check(hp(st, "pending", "goblin-1") == 7, "pending matches committed after PC commit")

    # --- combat_step 2: advance into goblin-1, then it acts -------------------
    step = game.combat_step()
    check(step.kind == "await_confirm", "NPC turn awaits confirm")
    check(step.combatant == "goblin-1", "the acting combatant is goblin-1")
    check(st.turn == "goblin-1", "combat_step advanced the turn pointer to goblin-1")
    check(hp(st, "committed", "pc") == 30,
          "committed == goblin-1's post-advance start (PC unhurt in committed)")
    check(hp(st, "pending", "pc") == 24, "goblin-1's 6 damage lives only in pending")

    # --- interject: rollback to goblin-1's start, replay with the reaction ----
    step = game.combat_interject("I cast shield!")
    check(step.kind == "await_confirm", "interject re-presents for confirm")
    check(hp(st, "committed", "pc") == 30, "committed untouched by the rolled-back action")
    check(hp(st, "pending", "pc") == 28,
          "rollback restored pending to 30, replay then applied the blunted 2 damage")

    # --- confirm: harden the replayed beat ------------------------------------
    game.combat_confirm()
    check(hp(st, "committed", "pc") == 28, "confirm hardened the replayed action into committed")

    # --- combat_step 3: advance into goblin-2, which ends the fight -----------
    step = game.combat_step()
    check(step.kind == "ended", "end_encounter ends the combat loop")
    check(not game.in_combat, "in_combat flips back to False")
    check(not st.exists(), "the tracker state file is gone after end_encounter")
    check(backend.i == len(script), "every scripted model call was consumed, in order")

    print("\nC1 combat loop: all boundaries correct.")


if __name__ == "__main__":
    main()
