#!/usr/bin/env python3
"""Standalone check for the combat mode-switch loop (design/combat.md § The combat loop) — no pytest, no
opencode, no model. Run me directly.

Drives the real `Game` combat surface over a fake backend that simulates the tracker
plugin's effect on the state file (start_encounter seeds it; advance_turn moves the
top-level turn pointer; damage mutates `pending`; end_encounter deletes it). The point
is the **commit/rollback boundaries**: after each step we read the state file and assert
`committed` vs. `pending` are exactly where the invariant says they should be —

  - the PC's own turn commits directly (no confirm gate);
  - an NPC turn resolves the action into `pending` (advancing the turn pointer as its
    closing act) while `committed` still holds that combatant's pre-action start, awaiting
    confirm;
  - an interject rolls `pending` back to `committed` (turn pointer restored) and replays;
  - a bare confirm hardens `pending` into `committed`;
  - end_encounter leaves combat and drops the file.

Every turn ends by advancing (advance-at-end), so the turn pointer travels inside the
committed/pending frames — which is what makes the interject rollback land on the right
combatant.

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
from gm_llm.orchestrator.logs import Logs  # noqa: E402


# ── fakes ───────────────────────────────────────────────────────────────────

class _Reply:
    rolls = ()

    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = set(tools)
        self.tool_inputs = tool_inputs or {}


def _initial_state():
    def c(cid, name, hp, x, y):
        return {"id": cid, "name": name, "hp": hp, "hp_max": hp, "dead": False,
                "conditions": [], "reaction": True, "x": x, "y": y, "z": 0}
    frame = {
        "turn": "pc", "round": 1,  # turn/round live in the frame, so commit/rollback carry them
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


# ── state-file mutations the fake backend applies ─────────────────────────────

def m_start(directory):
    CombatState(directory).save(_initial_state())


def _advance_pending(s):
    """Move the pending turn pointer to the next combatant (the plugin's advance_turn)."""
    init = s["pending"]["initiative"]
    ni = (init.index(s["pending"]["turn"]) + 1) % len(init)
    if ni == 0:
        s["pending"]["round"] += 1
    s["pending"]["turn"] = init[ni]


def m_act(cid, amt):
    """A whole turn's effect: damage `cid` in pending, then advance — the runner resolves
    its action and ends the turn with advance_turn, in one call."""
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


# ── assertions helpers ────────────────────────────────────────────────────────

def hp_frame(frame, cid):
    return frame["combatants"][cid]["hp"]


def hp(st, frame, cid):
    return st.load()[frame]["combatants"][cid]["hp"]


def turn_of(st, frame):
    return st.load()[frame]["turn"]


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
        # 2. PC's turn: strike goblin-1 for 5, then advance (pc -> goblin-1)
        ("You lunge; your blade bites deep.", {"damage", "advance_turn"}, m_act("goblin-1", 5)),
        # 3. goblin-1's turn: hit the PC for 6, then advance (goblin-1 -> goblin-2)
        ("The goblin's blade rakes your side.", {"damage", "advance_turn"}, m_act("pc", 6)),
        # 4. interject replay: shield blunts it to 2, then advance (goblin-1 -> goblin-2)
        ("Your shield flares; the blow glances off.", {"damage", "advance_turn"}, m_act("pc", 2)),
        # 5. goblin-2's turn: it breaks and the fight ends
        ("The last goblin turns and flees into the dark.", {"end_encounter"}, m_end),
    ]
    backend = FakeBackend(tmp, script)
    logs = Logs.under(base=Path(tmp) / "logs")
    game = Game(backend, None, campaign_dir=tmp, session=1, transcript=False, logs=logs)
    st = CombatState(tmp)

    check(not game.in_combat, "not in combat before start_encounter")

    # --- enter combat via a normal player-driven turn -------------------------
    tr = game.turn("I ready my blade.")
    check(tr.combat_started, "turn() reports combat_started on start_encounter")
    check(game.in_combat, "in_combat flips True after start_encounter")

    # --- combat_step 1: the PC is up ------------------------------------------
    step = game.combat_step()
    check(step.kind == "await_pc", "first combat_step yields the PC's turn")
    check(st.turn == "pc", "the PC is the opening combatant (start_encounter seated them)")

    # --- PC acts: resolves + advances as its closing act, commits directly ----
    step = game.combat_player_action("I attack the nearer goblin.")
    check(step.kind == "committed", "PC action commits directly (no confirm gate)")
    check(turn_of(st, "committed") == "goblin-1", "the PC's closing advance moved the pointer")
    check(hp(st, "committed", "goblin-1") == 7, "PC's 5 damage hardened into committed")
    check(hp(st, "pending", "goblin-1") == 7, "pending matches committed after PC commit")

    # --- combat_step 2: goblin-1 acts (and advances), awaiting confirm --------
    step = game.combat_step()
    check(step.kind == "await_confirm", "NPC turn awaits confirm")
    check(step.combatant == "goblin-1", "the acting combatant is goblin-1")
    check(turn_of(st, "committed") == "goblin-1",
          "committed still holds goblin-1's pre-action start")
    check(turn_of(st, "pending") == "goblin-2", "pending advanced past goblin-1 as its closing act")
    check(hp(st, "committed", "pc") == 30, "committed PC unhurt (the hit lives only in pending)")
    check(hp(st, "pending", "pc") == 24, "goblin-1's 6 damage is in pending")

    # --- interject: rollback to goblin-1's start, replay with the reaction ----
    step = game.combat_interject("I cast shield!")
    check(step.kind == "await_confirm", "interject re-presents for confirm")
    check(step.combatant == "goblin-1", "the rollback restored the pointer to goblin-1")
    check(hp(st, "committed", "pc") == 30, "committed untouched by the rolled-back action")
    check(hp(st, "pending", "pc") == 28,
          "rollback restored pending to 30, replay then applied the blunted 2 damage")

    # --- confirm: harden the replayed beat ------------------------------------
    game.combat_confirm()
    check(hp(st, "committed", "pc") == 28, "confirm hardened the replayed action into committed")
    check(turn_of(st, "committed") == "goblin-2", "committed now carries the advance to goblin-2")

    # --- combat_step 3: goblin-2 acts and ends the fight ----------------------
    step = game.combat_step()
    check(step.kind == "ended", "end_encounter ends the combat loop")
    check(not game.in_combat, "in_combat flips back to False")
    check(not st.exists(), "the tracker state file is gone after end_encounter")
    check(backend.i == len(script), "every scripted model call was consumed, in order")

    # --- every combat beat is archived with the tracker frames around it ------
    import json
    turns = [json.loads(l) for l in logs.archive.path.read_text().splitlines()
             if json.loads(l)["event"] == "turn"]
    beats = [e for e in turns if "combat" in e]
    check([e["combat"]["combatant"] for e in beats] == ["pc", "goblin-1", "goblin-1", "goblin-2"],
          "the PC action, goblin-1, its replay and the exit beat are archived as combat beats")
    pc_beat = beats[0]["combat"]
    check(pc_beat["before"] and pc_beat["after"]
          and hp_frame(pc_beat["before"], "goblin-1") == 12
          and hp_frame(pc_beat["after"], "goblin-1") == 7,
          "a beat carries the committed frame before it and the pending frame after it")

    print("\ncombat loop: all boundaries correct, every beat archived with its frames.")


# ── resume mid-combat recovery ────────────────────────────────────────────────

def _await_confirm_state():
    """The persisted tracker state at the instant an NPC action awaits confirm: committed
    still holds goblin-1's pre-action start; pending holds the applied hit and the closing
    advance. If the process dies here (before confirm), a resume must not skip the gate."""
    s = _initial_state()
    for frame in ("committed", "pending"):
        s[frame]["turn"] = "goblin-1"
    s["pending"]["combatants"]["pc"]["hp"] = 24   # goblin-1's 6 damage, in pending only
    _advance_pending(s)                            # pending's closing advance: goblin-1 -> goblin-2
    return s


def resume_recovery():
    """A crash between drafting goblin-1's action and confirming it leaves an in-flight
    `pending` with no in-memory `_combat_pending`. On resume, `combat_step` must roll it
    back and re-resolve goblin-1 through the confirm gate — never commit it blind or skip
    to goblin-2 (which would drop the confirm gate and lose the un-appended narration)."""
    tmp = tempfile.mkdtemp()
    CombatState(tmp).save(_await_confirm_state())   # the persisted crash state
    # One scripted reply: the fresh re-resolution of goblin-1's turn.
    script = [("The goblin's blade rakes your side.", {"damage", "advance_turn"}, m_act("pc", 6))]
    backend = FakeBackend(tmp, script)
    game = Game(backend, None, campaign_dir=tmp, session=1, transcript=False)
    st = CombatState(tmp)

    check(game.in_combat, "resume into a live tracker file flips in_combat True")
    check(st.in_flight(), "resume sees an in-flight uncommitted action (committed != pending)")

    step = game.combat_step()
    check(step.kind == "await_confirm", "resume re-resolves the interrupted combatant, awaiting confirm")
    check(step.combatant == "goblin-1", "goblin-1 is re-resolved, not skipped to goblin-2")
    check(hp(st, "committed", "pc") == 30, "the uncommitted action was rolled back — committed PC unhurt")
    check(hp(st, "pending", "pc") == 24, "goblin-1's turn re-applied fresh in pending")
    check(turn_of(st, "committed") == "goblin-1", "committed restored to goblin-1's pre-action start")
    check(turn_of(st, "pending") == "goblin-2", "the re-resolution's closing advance moved pending on")
    check(backend.i == len(script), "exactly one re-resolution call was consumed")

    print("resume recovery: a crash mid-confirm rolls back and re-resolves, gate intact.")


if __name__ == "__main__":
    main()
    resume_recovery()
