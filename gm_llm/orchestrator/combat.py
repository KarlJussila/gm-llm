"""
Combat mode — the initiative-driven loop that replaces the player-driven `turn()`
while a fight is on (COMBAT.md C1).

Out of combat the *player* drives: one message → one gated DM response. In combat
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
wrong combatant — see COMBAT.md "The combat loop".)

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
      await_confirm — an NPC acted (`narration` is the gated beat): present it, then
                      `combat_confirm()` on a bare Enter or `combat_interject(text)`.
      committed     — a PC action resolved and was committed (no confirm gate).
      ended         — the runner called `end_encounter`; combat is over, resume play.
    """
    kind: str
    combatant: str | None = None
    round: int | None = None
    narration: str = ""
    gate: "GateResult | None" = None  # noqa: F821 — annotation only
    corrected: bool = False


# --- briefs -----------------------------------------------------------------
# C1 scaffolding: minimal, functional prompts so the plumbing runs end to end. The
# combat play-craft (the per-combatant algorithm, proactive-pause discipline, the
# repertoire consult, real lethality) is C5 — `combat-reminder` / `combat-run` — and
# replaces these. They are inert under the mock backend that C1 is verified against.
#
# Every turn ends with advance_turn — that closing advance is what seats the next
# combatant and fires their timers, and it is what a rollback rewinds on an interject.

_ADVANCE_NUDGE = (
    "You resolved the action but didn't end the turn — call `advance_turn` now to pass "
    "initiative to the next combatant, and nothing else."
)


def _npc_brief(combatant: str) -> str:
    return (
        f"It is {combatant}'s turn. Resolve this one combatant's action: consult the "
        f"tracker, apply the results with its tools (damage/move/condition/…), and "
        f"narrate the beat. End the turn by calling `advance_turn`."
    )


def _pc_brief(player_input: str) -> str:
    return (
        "It is the PC's turn. Adjudicate the player's action below, apply the results "
        "with the tracker's tools, and narrate the outcome. End the turn by calling "
        "`advance_turn`.\n\n"
        f"<player>\n{player_input}\n</player>"
    )


def _replay_brief(combatant: str, text: str) -> str:
    return (
        f"The player interjects before {combatant}'s action resolves — treat it as a "
        f"reaction. The tracker has been rolled back to the start of {combatant}'s turn. "
        f"Replay the turn with the reaction below folded in, apply the results, narrate, "
        f"and end the turn by calling `advance_turn`.\n\n<reaction>\n{text}\n</reaction>"
    )


class CombatMixin:
    """The combat loop surface, mixed into `Game` (which supplies `backend`, `gate`,
    `runner_sid`, `_step`, `_run_gate`, `_append_transcript`). Kept in its own module
    so the play-driven `turn()` loop and the initiative-driven combat loop stay legible
    side by side."""

    # These are initialised in Game.__init__; declared here for reference.
    _in_combat: bool
    _combat_pending: CombatStep | None

    @property
    def in_combat(self) -> bool:
        return self._in_combat

    def _combat_observe(self, reply) -> None:
        """Flip mode on the runner's entry/exit signals, read off a turn's tool calls.
        Called from `_gated_turn`, so a `start_encounter` mid-narration switches the
        interface into the combat loop after this turn returns."""
        if "start_encounter" in reply.tools:
            self._in_combat = True
            self._combat_pending = None
        if "end_encounter" in reply.tools:
            self._in_combat = False

    def combat_step(self) -> CombatStep:
        """Dispatch the current combatant: hand back to the player (PC turn) or resolve
        one NPC action (awaiting confirm). The tracker's turn pointer — advanced by the
        previous turn's closing `advance_turn` — is the loop's cursor; no advance happens
        here."""
        st = CombatState(self.backend.directory)
        if not st.exists():
            self._in_combat = False
            return CombatStep(kind="ended")

        up = st.turn
        rnd = st.round
        if up == "pc":
            return CombatStep(kind="await_pc", combatant="pc", round=rnd)

        # NPC turn: the runner resolves one combatant's action and ends it by advancing.
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _npc_brief(up))
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line="")
        self._ensure_advanced(st, up)
        final, result, corrected = self._run_gate(reply.text, f"(combat: {up}'s turn)")
        self._step("done")
        step = CombatStep(kind="await_confirm", combatant=up, round=rnd,
                          narration=final, gate=result, corrected=corrected)
        self._combat_pending = step
        return step

    def _ensure_advanced(self, st: CombatState, acted: str) -> None:
        """The runner ends its turn by calling `advance_turn`. If the pointer didn't move
        off `acted`, it forgot — nudge once so initiative doesn't stall. (A missed advance
        is benign and self-evident; the old separate advance step's failure mode — the
        model over-acting on an 'advance only' prompt — does not exist here.)"""
        if st.turn == acted:
            self.backend.prompt_full(self.runner_sid, self.runner_agent, _ADVANCE_NUDGE)

    def combat_confirm(self) -> CombatStep | None:
        """Bare-Enter confirm of the NPC action awaiting confirm: harden it into
        `committed` and record the beat. `combat_step` then reads the already-advanced
        turn pointer to reach the next combatant."""
        CombatState(self.backend.directory).commit()
        step = self._combat_pending
        self._combat_pending = None
        if step:
            self._append_transcript("", step.narration, opening=False, dm_only=True)
        return step

    def combat_interject(self, text: str) -> CombatStep:
        """The player reacts before the NPC action resolves. Roll `pending` back to this
        combatant's start (the turn pointer comes back with it), replay the turn with the
        reaction folded in, gate, and present for confirm again — a missed pause stays
        cheap."""
        st = CombatState(self.backend.directory)
        st.rollback()
        up = st.turn  # rollback restored the pointer to the interrupted combatant
        rnd = st.round
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _replay_brief(up, text))
        self._ensure_advanced(st, up)
        final, result, corrected = self._run_gate(reply.text, f"(combat reaction: {text})")
        self._step("done")
        step = CombatStep(kind="await_confirm", combatant=up, round=rnd,
                          narration=final, gate=result, corrected=corrected)
        self._combat_pending = step
        return step

    def combat_player_action(self, player_input: str) -> CombatStep:
        """The PC's turn: adjudicate the player's action, gate, and commit directly — a
        player's own turn has no confirm gate (it is symmetric to an NPC turn for commit
        purposes, retconnable within its window, but the player does not confirm their own
        beat). The action ends by advancing, same as any turn."""
        st = CombatState(self.backend.directory)
        rnd = st.round
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _pc_brief(player_input))
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line=player_input)
        self._ensure_advanced(st, "pc")
        final, result, corrected = self._run_gate(reply.text, player_input)
        st.commit()
        self._append_transcript(player_input, final, opening=False)
        self._step("done")
        return CombatStep(kind="committed", combatant="pc", round=rnd,
                          narration=final, gate=result, corrected=corrected)

    def _combat_end(self, narration: str, player_line: str) -> CombatStep:
        """The runner called `end_encounter` (all foes down or withdrawn). Gate the final
        beat, leave combat, and let the state file go (the plugin already deleted it)."""
        final, result, corrected = self._run_gate(narration, player_line or "(combat ends)")
        self._in_combat = False
        self._combat_pending = None
        self._append_transcript(player_line, final, opening=False, dm_only=not player_line)
        CombatState(self.backend.directory).delete()
        return CombatStep(kind="ended", combatant=None, narration=final,
                          gate=result, corrected=corrected)
