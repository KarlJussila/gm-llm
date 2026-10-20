"""
Combat mode — the initiative-driven loop that replaces the player-driven `turn()`
while a fight is on (design/combat.md § The combat loop).

Out of combat the *player* drives: one message → one DM response. In combat
*initiative* drives: the orchestrator pumps the loop, soliciting the player on the
PC's turn and narrating one combatant per NPC turn. The runner signals entry/exit by
calling the `start_encounter` / `end_encounter` tracker tools (observed off
`reply.tools`, like `task_complete`); the orchestrator flips `_in_combat`, which
selects the driver.

**The one load-bearing invariant — the snapshot carries the turn pointer.** The
tracker state file keeps two frames, `committed` (hardened truth) and `pending` (the
action in flight), and each frame carries its own `turn`/`round`. A commit copies
pending→committed; a rollback copies committed→pending — the turn pointer included.
So the runner ends its turn by calling `advance_turn` as its closing act, and:

  committed  ==  this combatant's turn, before they acted (their timers already fired
                 by the previous combatant's closing advance)

The action call mutates `pending` and advances its turn pointer to the next
combatant. On confirm we commit. On interject we roll `pending` back to `committed`
— which restores the turn pointer to *this* combatant — and replay their turn; no
double-fired timers, no wrong-combatant replay. (Because the turn pointer travels in
the snapshot, the advance can safely live at the end of the action call; were it
top-level and shared, a rollback couldn't rewind it and the replay would resolve the
wrong combatant — see design/combat.md "The combat loop".)

The orchestrator owns only the two frame swaps (commit/rollback); every semantic
mutation — damage, move, advance_turn — is the model calling a tracker tool, which
the TS engine applies. `next_timer_id` stays top-level so a rolled-back timer's id is
never reused.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path



def combat_state_path(directory: str) -> Path:
    """The tracker's state file — the same path `plugin/combat-tracker.ts` writes."""
    return Path(directory) / ".opencode" / ".orchestrator" / "combat-state.json"


class CombatState:
    """A thin read/modify/write wrapper over the tracker's state file. The orchestrator
    only ever performs the two frame swaps here — `commit` and `rollback`; every
    semantic mutation (damage, move, advance_turn, …) is the model calling a tracker
    tool, which the TS engine applies. `turn`/`round` live inside each frame, so the
    swaps carry them; `next_timer_id` is top-level and never rewinds."""

    def __init__(self, directory: str):
        self.path = combat_state_path(directory)

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def commit(self) -> None:
        """Harden the in-flight action: pending → committed (turn pointer included)."""
        s = self.load()
        s["committed"] = copy.deepcopy(s["pending"])
        self.save(s)

    def rollback(self) -> None:
        """Undo the in-flight action: committed → pending. Restores the turn pointer to
        this combatant, so the replay resolves the right one."""
        s = self.load()
        s["pending"] = copy.deepcopy(s["committed"])
        self.save(s)

    def in_flight(self) -> bool:
        """True when `pending` holds an action not yet committed — the two frames differ.
        In normal operation `combat_step` is only ever entered from a just-committed state
        (equal frames); a differing pair means a crash/resume interrupted an action between
        drafting it and confirming it, so the resume guard rolls it back and re-resolves."""
        if not self.exists():
            return False
        s = self.load()
        return s["committed"] != s["pending"]

    @property
    def turn(self) -> str | None:
        return self.load()["pending"]["turn"] if self.exists() else None

    @property
    def round(self) -> int | None:
        return self.load()["pending"]["round"] if self.exists() else None

    def is_pc_turn(self) -> bool:
        return self.turn == "pc"

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class CombatStep:
    """One pump of the combat loop. `kind` tells the interface what to do next:

      await_pc      — the PC's turn: solicit input, then call `combat_player_action`.
      await_confirm — an NPC acted (`narration` is the beat): present it, then
                      `combat_confirm()` on a bare Enter or `combat_interject(text)`.
      committed     — a PC action resolved and was committed (no confirm gate).
      ended         — the DM called `end_encounter`; combat is over, resume play.
    """
    kind: str
    combatant: str | None = None
    round: int | None = None
    narration: str = ""


# --- messages ---------------------------------------------------------------
# Each combat step tells the DM only what changed: whose turn it is, the player's action, or
# the reaction being folded in. The craft lives in the `combat-run` skill. Every turn ends with
# advance_turn — that closing advance seats the next combatant and fires their timers, and it is
# what a rollback rewinds on an interject.

_ADVANCE_NUDGE = (
    "You resolved the action but didn't end the turn — call `advance_turn` now to pass "
    "initiative to the next combatant, and nothing else."
)


def _npc_brief(combatant: str) -> str:
    return f"<combat-turn>\nIt is {combatant}'s turn.\n</combat-turn>"


def _pc_brief(player_input: str) -> str:
    return ("<combat-turn>\nIt is the PC's turn — adjudicate the player's action.\n</combat-turn>\n"
            f"<player>\n{player_input}\n</player>")


def _replay_brief(combatant: str, text: str) -> str:
    return (f"<combat-reaction>\nThe player interjects before {combatant}'s action resolves — treat "
            f"it as a reaction. The tracker was rolled back to the start of {combatant}'s turn; "
            f"replay the turn with the reaction folded in.\n<reaction>\n{text}\n</reaction>\n"
            f"</combat-reaction>")


class CombatMixin:
    """The combat loop surface, mixed into `Game` (which supplies `backend`, `runner_sid`,
    `_step`, `_append_transcript`, `_archive_turn`). Kept in its own module so the
    play-driven `turn()` loop and the initiative-driven combat loop stay legible side by side."""

    # These are initialised in Game.__init__; declared here for reference.
    _in_combat: bool
    _combat_pending: CombatStep | None

    @property
    def in_combat(self) -> bool:
        return self._in_combat

    def _combat_observe(self, reply) -> None:
        """Flip mode on the DM's entry/exit signals, read off a turn's tool calls."""
        if "start_encounter" in reply.tools:
            self._in_combat = True
            self._combat_pending = None
        if "end_encounter" in reply.tools:
            self._in_combat = False

    def _beat(self, message: str, player_line: str, combatant: str, st: CombatState):
        """Send one combat message and archive the beat with the tracker frames on either
        side of it — what the after-play combat check compares the narration against."""
        before = st.load().get("committed") if st.exists() else None
        self._turn_no += 1
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, message)
        if "end_encounter" not in reply.tools:
            self._ensure_advanced(st, combatant)
        self._step("done")
        after = st.load().get("pending") if st.exists() else None
        self._archive_combat(player_line, reply, combatant, before, after)
        return reply

    def _archive_combat(self, player_line, reply, combatant, before, after) -> None:
        if not (self.logs and self.logs.archive):
            return
        cu = self.backend.context_usage(self.runner_sid)
        self.logs.archive.emit(
            "turn", session=self.session, turn=self._turn_no, opening=False,
            player=player_line, narration=reply.text, session_complete=False,
            close_nudged=False, tools=sorted(reply.tools),
            context=({"tokens": cu.tokens, "limit": cu.context_limit} if cu else None),
            combat={"combatant": combatant, "before": before, "after": after},
        )

    def combat_step(self) -> CombatStep:
        """Dispatch the current combatant: hand back to the player (PC turn) or resolve one
        NPC action (awaiting confirm). The tracker's turn pointer is the loop's cursor."""
        st = CombatState(self.backend.directory)
        if not st.exists():
            self._in_combat = False
            return CombatStep(kind="ended")

        # Resume recovery: `pending` still holds an uncommitted action (a crash between
        # resolving an action and confirming it) with no in-memory step to present — roll it
        # back to the last committed truth and re-resolve the interrupted combatant.
        if self._combat_pending is None and st.in_flight():
            st.rollback()

        up = st.turn
        rnd = st.round
        if up == "pc":
            return CombatStep(kind="await_pc", combatant="pc", round=rnd)

        reply = self._beat(_npc_brief(up), f"(combat: {up}'s turn)", up, st)
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line="")
        step = CombatStep(kind="await_confirm", combatant=up, round=rnd, narration=reply.text)
        self._combat_pending = step
        return step

    def _ensure_advanced(self, st: CombatState, acted: str) -> None:
        """The DM ends its turn by calling `advance_turn`. If the pointer didn't move off
        `acted`, it forgot — nudge once so initiative doesn't stall."""
        if st.exists() and st.turn == acted:
            self.backend.prompt_full(self.runner_sid, self.runner_agent, _ADVANCE_NUDGE)

    def combat_confirm(self) -> CombatStep | None:
        """Bare-Enter confirm of the NPC action awaiting confirm: harden it into `committed`
        and record the beat."""
        CombatState(self.backend.directory).commit()
        step = self._combat_pending
        self._combat_pending = None
        if step:
            self._append_transcript("", step.narration, opening=False, dm_only=True)
        return step

    def combat_interject(self, text: str) -> CombatStep:
        """The player reacts before the NPC action resolves. Roll `pending` back to this
        combatant's start, replay the turn with the reaction folded in, and present it for
        confirm again."""
        st = CombatState(self.backend.directory)
        st.rollback()
        up = st.turn
        rnd = st.round
        reply = self._beat(_replay_brief(up, text), f"(combat reaction: {text})", up, st)
        step = CombatStep(kind="await_confirm", combatant=up, round=rnd, narration=reply.text)
        self._combat_pending = step
        return step

    def combat_player_action(self, player_input: str) -> CombatStep:
        """The PC's turn: adjudicate the player's action and commit directly — a player's own
        turn has no confirm gate."""
        st = CombatState(self.backend.directory)
        rnd = st.round
        reply = self._beat(_pc_brief(player_input), player_input, "pc", st)
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line=player_input)
        st.commit()
        self._append_transcript(player_input, reply.text, opening=False)
        return CombatStep(kind="committed", combatant="pc", round=rnd, narration=reply.text)

    def _combat_end(self, narration: str, player_line: str) -> CombatStep:
        """The DM called `end_encounter`. Leave combat and let the state file go."""
        self._in_combat = False
        self._combat_pending = None
        self._append_transcript(player_line, narration, opening=False, dm_only=not player_line)
        CombatState(self.backend.directory).delete()
        return CombatStep(kind="ended", combatant=None, narration=narration)


# --- driver -----------------------------------------------------------------
# The one home for combat's *sequencing policy*. The engine above (`CombatMixin`) owns
# the per-combatant mechanics — resolve, gate, commit/rollback; the driver owns the loop
# *around* them: pump NPC beats, confirm each, stop at a PC slot or the fight's end, thread
# interjections and cancels. Every interface drives a fight through this and stays mechanical —
# render a beat, get input, call the next method — so no combat policy ever leaks into an
# interface. `play_combat` below wraps the driver with the player prompting and turn
# accounting, and is what `play.play_session` hands a fight to — so a human at the TUI and an
# unattended `bench run` fight through the same code, differing only in their `PlayerSource`.
# See design/combat.md "The combat loop".


@dataclass
class CombatEvent:
    """What the driver hands an interface after a pump — where the loop stopped and why:

      pc_slot — the PC's turn: solicit the player's action, then call `pc_action(text)`.
      ended   — the fight is over; `narration` is the exit beat. Resume normal play with
                it as the current scene.
    """
    kind: str
    combatant: str | None = None
    round: int | None = None
    narration: str = ""


class CombatDriver:
    """The pull-based combat loop, policy in the library ONCE. Wraps a `Game` and pumps
    its initiative surface (`combat_step`/`combat_player_action`/`combat_confirm`/
    `combat_interject`), stopping only where an interface must act: the PC's slot, or the
    end of the fight.

    `on_beat(narration, combatant) -> str | None` is the interface's sole hook. The driver
    calls it to *render* each resolved beat as it happens; for an NPC beat awaiting confirm,
    the hook's RETURN value is also its confirm channel — return an interjection (a PC
    reaction) to fold it in before the beat commits (the tracker rolls back, the turn
    replays, and the new beat is re-presented — a reaction to a reaction stays cheap), or
    return None/'' to confirm and advance. An agent player passes a render-only hook (always
    None); the TUI's blocks for the human's Enter-or-react. A PC beat is rendered through the
    hook too, with its return ignored (it commits directly). The **exit** beat is not: it
    rides back on the `ended` event, for the caller to hand to normal play.

    Cancel survives: a `BackendCancelled` raised while a beat is drafting propagates straight
    out — the engine's in-flight rollback / resume guard (`CombatState.in_flight`) keeps the
    tracker consistent, so the caller reverts the runner session and re-enters through
    `advance` again. Resume-mid-combat needs nothing special: a fresh `Game` whose `_in_combat`
    recovered off the state file is driven by calling `advance` on it."""

    def __init__(self, game: "Game"):  # noqa: F821 — Game imports this module
        self.game = game

    @property
    def in_combat(self) -> bool:
        return self.game.in_combat

    def advance(self, on_beat=None) -> CombatEvent:
        """Pump NPC beats until the PC's slot or the fight's end, presenting and confirming
        each along the way. Returns a `pc_slot` or `ended` event."""
        while True:
            step = self.game.combat_step()
            if step.kind == "await_pc":
                return CombatEvent("pc_slot", combatant=step.combatant, round=step.round)
            if step.kind == "ended":
                return CombatEvent("ended", narration=step.narration)
            # await_confirm: an NPC resolved its action. Present it; a returned reaction
            # interjects and re-presents (re-confirmable) until the player is done reacting.
            self._settle(step, on_beat)

    def pc_action(self, text: str, on_beat=None) -> CombatEvent:
        """Play the PC's slot (committed directly — no confirm gate), then resume pumping
        to the next PC slot or the fight's end."""
        step = self.game.combat_player_action(text)
        if step.kind == "ended":
            return CombatEvent("ended", narration=step.narration)
        if on_beat:
            on_beat(step.narration, "pc")  # the committed PC beat — render only, no confirm
        return self.advance(on_beat=on_beat)

    def interject(self, text: str, on_beat=None) -> CombatEvent:
        """Fold a PC reaction into the NPC beat currently awaiting confirm, then carry on
        pumping. A pass-through for interfaces that surface the confirm gate as an explicit
        step rather than through `on_beat`'s return value; both routes reach the same engine
        method. Legal only while an NPC beat awaits confirm (an in-flight `_combat_pending`)."""
        step = self.game.combat_interject(text)
        self._settle(step, on_beat)
        return self.advance(on_beat=on_beat)

    def _settle(self, step: CombatStep, on_beat) -> None:
        """Present an NPC beat awaiting confirm and resolve the confirm gate: a returned
        reaction interjects and re-presents (looping, so a reaction to a reaction stays
        cheap); anything falsy confirms and hardens the beat."""
        reaction = on_beat(step.narration, step.combatant) if on_beat else None
        while reaction:
            step = self.game.combat_interject(reaction)
            reaction = on_beat(step.narration, step.combatant) if on_beat else None
        self.game.combat_confirm()


@dataclass
class CombatRun:
    """How a fight left the loop, and what normal play resumes from.

      scene   — the narration to carry forward: the exit beat, or the last beat seen if the
                fight was cut short.
      turns   — the running turn count, one per PC slot played.
      hit_cap — the cap tripped mid-fight. A cap breach like any other: an unfinished fight
                has no clean wrap.
      stopped — the source ended the session on a PC slot (a human frontend taking the loop
                down). The fight is still live; nothing about it is settled.
    """
    scene: str
    turns: int
    hit_cap: bool = False
    stopped: bool = False


def play_combat(game, source, entry_scene, hooks, *, turns: int = 0,
                turn_cap: int | None = None) -> CombatRun:
    """Drive a whole fight to its end — the one home for what every interface does once a turn
    reports `combat_started`. The sequencing policy is the driver's; this adds the two things
    around it that belong to no single interface: soliciting the player on each PC slot, and
    turn accounting.

    **Each PC slot counts as one turn against `turn_cap`** — a fight must not make a run
    uncappable, and a PC slot is the combat analogue of a normal player turn (the beat the
    player acts on). NPC beats are pumped and confirmed by the driver at no turn cost.
    `turn_cap=None` disables accounting entirely (the human frontend caps nothing).

    `source` and `hooks` are the play layer's contracts (`orchestrator/play.py`), duck-typed
    here so combat stays legible on its own: `source.next_message(scene, combat=True)` is the
    PC's action, and rendering rides on `hooks.on_slot` (a slot is up), `hooks.on_beat` (each
    resolved beat — its return interjects, see `CombatDriver`), `hooks.on_player` (the action
    that came back) and `hooks.on_combat_end` (the exit beat, which no other hook carries)."""
    driver = CombatDriver(game)
    state = {"scene": entry_scene}

    def beat(narration, who):
        state["scene"] = narration
        return hooks.on_beat(narration, who)

    event = driver.advance(beat)
    while event.kind == "pc_slot":
        if turn_cap is not None and turns >= turn_cap:
            return CombatRun(state["scene"], turns, hit_cap=True)
        turns += 1
        hooks.on_slot(event, turns)
        player = source.next_message(state["scene"], combat=True)
        if player is None:  # the player is done driving the loop — leave the fight standing
            return CombatRun(state["scene"], turns - 1, stopped=True)
        hooks.on_player(player, turns)
        event = driver.pc_action(player, beat)
    hooks.on_combat_end(event.narration)
    return CombatRun(event.narration, turns)
