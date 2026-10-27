"""
The session loop — one turn loop, whoever is playing and whatever is rendering it.

A played session is one shape: ask the player for their next message, play the gated turn,
render what came back, repeat until the runner wraps the session or the turn cap trips.

`play_session` is the one loop. The only thing that differs between a human at a keyboard
and the scripted `player` agent is **where the next message comes from** — a `PlayerSource`:

  * `AgentPlayer` — prompts an AI player agent. Its lead (the character packet, for one) and,
    on a resume, the story so far ride in front of its first message; everything after is the
    per-turn reminder alone.
  * `KeyboardPlayer` — blocks until the engine hands a line in from another thread.

Everything else is the loop's, once: the packet framing, turn-cap accounting, the handoff
into `play_combat` when a fight breaks out, the wrap signal. What happens is reported through
`PlayHooks` — one optional callback per event — which the engine turns into protocol events
and a headless bench run into progress notes.

**The loop blocks, deliberately.** The engine runs it on a thread of its own and feeds the
`KeyboardPlayer` and combat's confirm gate from the thread that receives commands.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from .backend import BackendError
from .combat import play_combat
from .prompts import load


# ── where the next player message comes from ─────────────────────────────────

class PlayerSource:
    """The player end of the loop: one method to ask it for a message, one to end it.

    `human` tells the engine whether the player is asked for input while the source waits —
    `awaiting` for a `KeyboardPlayer`, "the player is thinking" for an `AgentPlayer`. It is a rendering question, never a policy one; the
    loop itself treats every source identically."""

    human = False

    def __init__(self):
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped

    def stop(self) -> None:
        """End the session loop the next time the player is asked to speak. Graceful by
        construction: a turn already in flight finishes and is kept, rather than being thrown
        away half-played — which is what a frontend wrapping a session actually wants.
        Latches, so a stopped source stays stopped; use one per session loop."""
        self._stopped = True

    def next_message(self, scene: str, *, combat: bool = False) -> str | None:
        """The player's next message, given the scene they are responding to. `combat=True`
        on a PC combat slot, which an agent player sees marked `<combat-turn>`. Return `None` to end the session — the loop stops with outcome `"stopped"`."""
        raise NotImplementedError


class AgentPlayer(PlayerSource):
    """An AI player agent: the benchmark's `player`, or the autonomous `auto-player`.

    Its **first** message carries its lead (the character packet, for one), then (on a resume)
    the story so far,
    in front of the per-turn body; every later message is the body alone. That priming is
    what makes an unattended session playable at all, and it lives here so the console
    harness and `bench run` cannot frame it two subtly different ways — which they were one
    edit away from doing, having each spelled out the same bracketed heading themselves."""

    human = False

    def __init__(self, backend, session_id: str, *, lead: str = "",
                 story: str | None = None, agent: str = "player"):
        super().__init__()
        self.backend = backend
        self.session_id = session_id
        self.agent = agent
        self.lead = lead
        self.story = story
        self._primed = False

    def next_message(self, scene: str, *, combat: bool = False) -> str | None:
        if self._stopped:
            return None
        body = load("player-combat-turn" if combat else "player-turn").format(scene=scene)
        return self.backend.prompt(self.session_id, self.agent, self._prime(body))

    def _prime(self, body: str) -> str:
        """The first message only: the lead, the story so far, then the turn body."""
        if self._primed:
            return body
        self._primed = True
        parts = [self.lead] if self.lead else []
        if self.story:
            parts.append(load("player-story").format(story=self.story))
        parts.append(body)
        return "\n\n".join(parts)


class KeyboardPlayer(PlayerSource):
    """A human at a frontend. `next_message` parks the loop's thread until the frontend calls
    `submit(text)` from its own thread; the frontend's input handler is the producer.

    `stop()` additionally wakes a thread already parked here, which is why a frontend must
    call it on the way out: a thread parked forever keeps the interpreter's thread pool from
    joining at exit."""

    human = True

    def __init__(self):
        super().__init__()
        self._ready = threading.Event()
        self._message = ""

    def submit(self, text: str) -> None:
        self._message = text
        self._ready.set()

    def stop(self) -> None:
        super().stop()
        self._ready.set()

    def next_message(self, scene: str, *, combat: bool = False) -> str | None:
        if self._stopped:
            return None
        self._ready.wait()
        self._ready.clear()
        return None if self._stopped else self._message


# ── what the loop tells its frontend ─────────────────────────────────────────

def _noop(*_args, **_kwargs):
    return None


@dataclass
class PlayHooks:
    """The frontend's side of the loop: one optional callback per event, defaulting to a
    silent run. Every piece of narration the loop produces reaches a frontend through
    exactly one of these, so a frontend never has to infer a beat it wasn't handed.

      on_prompt(turns)          — about to ask the player for turn `turns`.
      on_player(text, turns)    — that message landed (the DM is next).
      on_turn(result)          — a gated turn resolved (`TurnResult`).
      on_slot(event, turns)     — a PC combat slot, counted as turn `turns`.
      on_beat(narration, who)   — a resolved combat beat. Its RETURN is the confirm channel:
                                  a reaction interjects, None/'' confirms (`CombatDriver`).
      on_combat_end(narration)  — the fight's exit beat, handed over as normal play resumes.
      on_interrupt(stage, exc, message) -> bool — a model call raised `BackendError`
                                  (`BackendCancelled` included) at `stage` ∈ player/turn/
                                  combat. Return True to keep the session going (the loop
                                  re-asks from the same scene, and the abandoned turn costs
                                  nothing); anything falsy re-raises. **No hook re-raises**,
                                  which is what the unattended callers want: a rate-limit
                                  give-up is theirs to record, not the loop's to paper over.
    """

    on_prompt: Callable[[int], None] = _noop
    on_player: Callable[[str, int], None] = _noop
    on_turn: Callable[[object], None] = _noop
    on_slot: Callable[[object, int], None] = _noop
    on_beat: Callable[[str, str], "str | None"] = _noop
    on_combat_end: Callable[[str], None] = _noop
    on_interrupt: "Callable[[str, Exception, str], bool] | None" = None


@dataclass
class PlayResult:
    """Where the session loop stopped, and what to carry forward.

      complete — the runner signalled the session's end (`task_complete`). The post-session
                 tail (handoff notes, reconcile) is the caller's, not the loop's.
      cap      — `turn_cap` turns played without a wrap. A safety net, not an ending.
      stopped  — the source returned None: the player is done driving this loop (a wrap
                 asked for mid-play, or the engine closing). Nothing about the session is settled.
    """

    outcome: str
    turns: int
    scene: str


# ── the loop ─────────────────────────────────────────────────────────────────

def play_session(game, source, scene: str, *, hooks: PlayHooks | None = None,
                 turns: int = 0, turn_cap: int | None = None) -> PlayResult:
    """Play `game` from `scene` until the runner wraps, the cap trips, or `source` stops.

    The opening is **not** here: a caller has already resumed or opened the session and hands
    in the scene the player is responding to (the same contract `play_combat` has). Neither is
    the tail — a `complete` run's handoff notes and reconcile belong to whoever asked for them.
    What is here is everything that used to be copied per interface.

    **Turn accounting is bench's, and a fight cannot outrun it.** `turns` counts player turns;
    `turn_cap=None` disables the cap entirely (the human frontend). Each PC combat slot counts
    as one turn (`play_combat`), so a fight can't make a run uncappable, and an interrupted
    turn costs nothing — a cancelled or failed turn leaves no trace in the transcript, canon or
    the archive, so it must not burn the cap either.

    **Combat is entered from the top of the loop, not from the turn that started it.** Any
    iteration that finds `game.in_combat` drives the fight through `play_combat`. A turn whose
    draft called `start_encounter` therefore enters on the next pass — and so does a session
    *resumed* into a live fight, which none of the agent-player callers handled before: they
    would have sent a normal turn into a live tracker.

    A turn that both wraps the session and starts a fight (a contradiction no runner should
    produce) is read as a wrap: the session is over, and opening a fight into it would be the
    worse of the two readings."""
    hooks = hooks or PlayHooks()
    while turn_cap is None or turns < turn_cap:
        checkpoint, stage, message = turns, "player", ""
        try:
            if game.in_combat:
                stage = "combat"
                run = play_combat(game, source, scene, hooks, turns=turns, turn_cap=turn_cap)
                scene, turns = run.scene, run.turns
                if run.hit_cap:
                    return PlayResult("cap", turns, scene)
                if run.stopped:
                    return PlayResult("stopped", turns, scene)
                continue

            hooks.on_prompt(turns + 1)
            message = source.next_message(scene)
            if message is None:
                return PlayResult("stopped", turns, scene)
            turns += 1
            hooks.on_player(message, turns)
            stage = "turn"
            result = game.turn(message)
        except BackendError as e:
            # The call didn't produce a result — a cancel (the player's own doing) or a
            # give-up after the retry ladder. Whether that ends the session is the
            # frontend's call, not the loop's: unattended callers have no hook and the
            # exception rides out to them intact.
            if not (hooks.on_interrupt and hooks.on_interrupt(stage, e, message)):
                raise
            turns = checkpoint  # the abandoned turn left no trace; it costs nothing
            continue

        scene = result.final
        hooks.on_turn(result)
        if result.session_complete:
            return PlayResult("complete", turns, scene)
    return PlayResult("cap", turns, scene)
