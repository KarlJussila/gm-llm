"""
Combat mode — the initiative-driven loop that replaces the player-driven `turn()`
while a fight is on (COMBAT.md C1).

Out of combat the *player* drives: one message → one gated DM response. In combat
*initiative* drives: the orchestrator pumps the loop, soliciting the player on the
PC's turn and narrating one combatant per NPC turn. The runner signals entry/exit by
calling the `start_encounter` / `end_encounter` tracker tools (observed off
`reply.tools`, like `task_complete`); the orchestrator flips `_in_combat`, which
selects the driver.

**The one load-bearing invariant — commit snapshots right after `advance_turn`.**
The tracker state file keeps two frames, `committed` (hardened truth) and `pending`
(the action in flight); `turn`/`round`/`next_timer_id` sit *top-level*, shared. A
commit copies pending→committed; a rollback copies committed→pending — frames only,
never the shared turn pointer. So the advance (which moves `turn` and fires the new
combatant's timers) must happen at the **top of each combatant's turn as its own
step**, with the commit taken immediately after and *before* the action:

    committed  ==  this combatant's post-advance start (their timers already fired)

Then the action mutates `pending` without touching `turn`; an interject rolls
`pending` back to `committed` with the turn pointer still on this combatant, and the
replay re-runs *this* combatant's action — no double-fired timers, no wrong-combatant
replay. Snapshotting before the advance, or letting the action call advance, would
strand the moved turn pointer on rollback (see COMBAT.md "The combat loop").

Because a plugin tool can only run inside a model turn (opencode exposes no
execute-a-tool endpoint), the advance is a real — if minimal — model call; the
orchestrator owns only the frame swaps (commit/rollback), never the tracker's
semantics, which stay solely in the TS engine.
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
    tool, which the TS engine applies. `turn`/`round`/`next_timer_id` are top-level and
    deliberately untouched by either swap (see the module docstring)."""

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
        """Harden the in-flight action: pending → committed (frame only)."""
        s = self.load()
        s["committed"] = copy.deepcopy(s["pending"])
        self.save(s)

    def rollback(self) -> None:
        """Undo the in-flight action: committed → pending (frame only). The turn
        pointer stays on this combatant, so the replay resolves the right one."""
        s = self.load()
        s["pending"] = copy.deepcopy(s["committed"])
        self.save(s)

    @property
    def turn(self) -> str | None:
        return self.load().get("turn") if self.exists() else None

    @property
    def round(self) -> int | None:
        return self.load().get("round") if self.exists() else None

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

_ADVANCE_BRIEF = (
    "It is the top of the next combatant's turn. Call `advance_turn` once to move "
    "initiative forward and surface any timers that fire now. Do not narrate or "
    "resolve any action yet — just advance."
)

_ADVANCE_NUDGE = (
    "The turn did not advance — call `advance_turn` now, and nothing else."
)


def _npc_brief(combatant: str) -> str:
    return (
        f"It is {combatant}'s turn. Resolve this one combatant's action: consult the "
        f"tracker, apply the results with its tools (damage/move/condition/…), and "
        f"narrate the beat. Do not advance the turn — that is handled for you."
    )


def _pc_brief(player_input: str) -> str:
    return (
        "It is the PC's turn. Adjudicate the player's action below, apply the results "
        "with the tracker's tools, and narrate the outcome. Do not advance the turn.\n\n"
        f"<player>\n{player_input}\n</player>"
    )


def _replay_brief(combatant: str, text: str) -> str:
    return (
        f"The player interjects before {combatant}'s action resolves — treat it as a "
        f"reaction. The tracker has been rolled back to the start of {combatant}'s turn. "
        f"Replay the turn with the reaction below folded in, apply the results, and "
        f"narrate. Do not advance the turn.\n\n<reaction>\n{text}\n</reaction>"
    )


class CombatMixin:
    """The combat loop surface, mixed into `Game` (which supplies `backend`, `gate`,
    `runner_sid`, `_step`, `_run_gate`, `_append_transcript`). Kept in its own module
    so the play-driven `turn()` loop and the initiative-driven combat loop stay legible
    side by side."""

    # These are initialised in Game.__init__; declared here for reference.
    _in_combat: bool
    _combat_first: bool
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
            self._combat_first = True   # start_encounter already positioned combatant 0
            self._combat_pending = None
        if "end_encounter" in reply.tools:
            self._in_combat = False

    def combat_step(self) -> CombatStep:
        """Advance into the current combatant's turn (firing their timers) and either
        hand back to the player (PC turn) or resolve one NPC action (awaiting confirm).
        The advance + commit at the top is the rollback baseline (see module docstring);
        it is skipped only on the very first step, since `start_encounter` already seated
        the opening combatant."""
        st = CombatState(self.backend.directory)
        if not st.exists():
            self._in_combat = False
            return CombatStep(kind="ended")

        if not self._combat_first:
            self._combat_advance(st)
        self._combat_first = False

        up = st.turn
        rnd = st.round
        if up == "pc":
            return CombatStep(kind="await_pc", combatant="pc", round=rnd)

        # NPC turn: resolve one combatant's action. The runner does NOT advance — that is
        # the orchestrator's separate step at the top of the next combat_step.
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _npc_brief(up))
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line="")
        final, result, corrected = self._run_gate(reply.text, f"(combat: {up}'s turn)")
        self._step("done")
        step = CombatStep(kind="await_confirm", combatant=up, round=rnd,
                          narration=final, gate=result, corrected=corrected)
        self._combat_pending = step
        return step

    def _combat_advance(self, st: CombatState) -> None:
        """Drive the turn-advance model call, then snapshot: committed := the just-entered
        combatant's post-advance start. Nudges once if the runner forgot to advance (the
        turn pointer would be unchanged)."""
        before = st.turn
        self._step("draft")
        self.backend.prompt_full(self.runner_sid, self.runner_agent, _ADVANCE_BRIEF)
        if st.turn == before:
            self.backend.prompt_full(self.runner_sid, self.runner_agent, _ADVANCE_NUDGE)
        st.commit()  # the rollback baseline for this combatant's turn

    def combat_confirm(self) -> CombatStep | None:
        """Bare-Enter confirm of the NPC action awaiting confirm: harden it into
        `committed` and record the beat. The next `combat_step` advances past it."""
        CombatState(self.backend.directory).commit()
        step = self._combat_pending
        self._combat_pending = None
        if step:
            self._append_transcript("", step.narration, opening=False, dm_only=True)
        return step

    def combat_interject(self, text: str) -> CombatStep:
        """The player reacts before the NPC action resolves. Roll `pending` back to this
        combatant's start (turn pointer intact), replay the turn with the reaction folded
        in, gate, and present it for confirm again — a missed pause stays cheap."""
        st = CombatState(self.backend.directory)
        st.rollback()
        up = st.turn
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _replay_brief(up, text))
        final, result, corrected = self._run_gate(reply.text, f"(combat reaction: {text})")
        self._step("done")
        step = CombatStep(kind="await_confirm", combatant=up, round=st.round,
                          narration=final, gate=result, corrected=corrected)
        self._combat_pending = step
        return step

    def combat_player_action(self, player_input: str) -> CombatStep:
        """The PC's turn: adjudicate the player's action, gate, and commit directly — a
        player's own turn has no confirm gate (it is symmetric to an NPC turn for commit
        purposes, retconnable within its window, but the player does not confirm their own
        beat)."""
        st = CombatState(self.backend.directory)
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, _pc_brief(player_input))
        if "end_encounter" in reply.tools:
            return self._combat_end(reply.text, player_line=player_input)
        final, result, corrected = self._run_gate(reply.text, player_input)
        st.commit()
        self._append_transcript(player_input, final, opening=False)
        self._step("done")
        return CombatStep(kind="committed", combatant="pc", round=st.round,
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
