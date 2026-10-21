"""
The engine — everything that decides what happens, behind a JSON protocol.

A frontend is a client: it sends commands and renders events. The protocol is defined in
design/frontends.md § The protocol. The engine owns one campaign's `Lifecycle`: the phase
machine, what a line of input is taken as, the interrupt policy, combat's confirm gate and
the spoiler-free labels. Every model call runs on the engine's own threads, so `send` never
blocks on one.

Subscribers are called on whichever engine thread produced the event, under the engine's
lock (that is what keeps events in one order), so a subscriber must not block — hand the
event to your own thread or queue.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from pathlib import Path

from .. import __version__
from ..orchestrator.backend import BackendCancelled
from ..orchestrator.play import PlayHooks, play_session

PROTOCOL = 1

# Spoiler-free labels for the stage keys Setup, the planner and the Reconciler announce.
STAGE_LABELS = {
    "setup": {
        "intake": "gathering your brief · building the world",
        "char": "creating your character",
        "arcs-state": "shaping the story and opening scene",
        "lint": "checking campaign files",
        "gate": "double-checking the campaign",
        "commit": "saving the campaign",
        "prep": "planning session 1",
    },
    "wrap": {
        "handoff": "jotting down the runner's notes",
        "digest": "reading back the session",
        "feedback": "noting your feedback",
        "canon": "filing what's new in the world",
        "arcs": "advancing the story",
        "state": "updating where things stand",
        "propagation": "double-checking everything lines up",
        "prep": "prepping the next session",
    },
}

_TURN_STEPS = {"draft": "the DM is writing", "done": "finishing up"}

# A file the DM writes during setup → a spoiler-free label (first match wins). Setup's
# authoring otherwise looks frozen for minutes.
_SETUP_ACTIVITY = (
    ("characters/", "building your character"),
    ("arcs/", "shaping the story"),
    ("world/", "fleshing out the world"),
    ("documents/", "writing the in-world documents"),
    ("state/", "setting the opening scene"),
    ("INDEX", "organizing the campaign"),
    ("campaign.md", "organizing the campaign"),
)


class Engine:
    """One campaign behind the protocol. `lifecycle` is a `Lifecycle` (or `MockLifecycle`);
    `cleanup` runs on close (the real backend's `stop`)."""

    def __init__(self, lifecycle, *, cleanup=None, turn_cap: int | None = None,
                 directory: str = ""):
        self.lc = lifecycle
        self._cleanup = cleanup
        self._turn_cap = turn_cap
        self._directory = directory
        self._subscribers = []
        self._lock = threading.RLock()

        self.phase = "starting"
        self.awaiting: str | None = None
        self.busy: str | None = None

        self._source = None          # the session loop's PlayerSource
        self._loop_live = False
        self._after_loop = None      # "wrap" when an advance took the loop down for it
        self._gate = threading.Event()
        self._reaction = None
        self._tap = None             # the live stream tap for the current phase
        self._turn = 0
        self._activity_seen: set[str] = set()
        self._closing = False

    # -- the surface ---------------------------------------------------------

    def subscribe(self, fn) -> None:
        self._subscribers.append(fn)

    def start(self) -> None:
        self.lc.backend.on_retry = self._retry
        self._emit("hello", protocol=PROTOCOL, version=__version__,
                   directory=self._directory, batch=False)
        if self.lc.phase == "setup":
            self._spawn(self._open_setup)
        elif self.lc.phase == "wrap_pending":
            n = self.lc.session
            self._notice(f"session {n} complete — reconcile and prep session {n + 1}, "
                         f"or quit and decide later", "rule")
            self._set(phase="complete")
        else:
            self._spawn(self._open_session)

    def send(self, cmd: dict) -> None:
        kind = cmd.get("type", "")
        text = str(cmd.get("text") or "").strip()
        with self._lock:
            if kind not in self.actions():
                self._emit("error", what=kind or "command",
                           message=f"not available now (phase {self.phase})")
                return
            if kind == "input":
                self._input(text)
            elif kind == "meta":
                self._meta(text)
            elif kind == "advance":
                self._advance()
            elif kind == "cancel":
                self._spawn(self.lc.game.abort)
            elif kind == "status":
                self._spawn(self._status)
            elif kind == "shutdown":
                self._spawn(self.close)

    def actions(self) -> list[str]:
        if self.phase in ("starting", "closed"):
            return []
        acts = ["status", "shutdown"]
        if self.awaiting:
            acts.append("input")
        if self.awaiting == "turn":
            acts.append("meta")
        if self._can_advance():
            acts.append("advance")
        if self.busy and self.phase == "play":
            acts.append("cancel")
        return acts

    def close(self) -> None:
        with self._lock:
            if self.phase == "closed":
                return
            self._closing = True
            self._release_loop()
            self._stop_tap()
            self._set(phase="closed", awaiting=None, busy=None)
        if self._cleanup:
            self._cleanup()

    # -- state and events ------------------------------------------------------

    def _emit(self, type_: str, **fields) -> None:
        event = {"type": type_, **fields}
        with self._lock:
            for fn in list(self._subscribers):
                try:
                    fn(event)
                except Exception:  # noqa: BLE001 — a broken frontend never takes play down
                    pass

    def _set(self, **changes) -> None:
        with self._lock:
            for k, v in changes.items():
                setattr(self, k, v)
            self._emit("state", phase=self.phase, session=self.lc.session,
                       awaiting=self.awaiting, busy=self.busy, player=self._player(),
                       in_combat=self._in_combat(), actions=self.actions())

    def _say(self, speaker: str, text: str, *, meta: bool = False, combatant=None) -> None:
        self._emit("say", speaker=speaker, text=text, meta=meta, combatant=combatant)

    def _notice(self, text: str, kind: str = "status") -> None:
        self._emit("notice", kind=kind, text=text)

    def _error(self, what: str, exc: Exception) -> None:
        self._emit("error", what=what, message=str(exc))

    def _player(self) -> str:
        return "auto" if getattr(self.lc, "player", "human") == "auto" else "human"

    def _in_combat(self) -> bool:
        game = getattr(self.lc, "game", None)
        return bool(game is not None and game.in_combat)

    def _can_advance(self) -> bool:
        if self.phase in ("setup_done", "ready", "complete"):
            return not self.busy
        if self.phase != "play" or self._in_combat() or self._after_loop:
            return False
        if self._loop_live:
            # An agent player is always mid-call; stopping it is graceful (the turn in
            # flight finishes and is kept), so a watched run can be wrapped any time.
            return self.awaiting == "turn" or self._player() == "auto"
        return not self.busy

    def _spawn(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _stream(self, kind: str, text: str) -> None:
        self._emit("stream", kind=kind, text=text)

    def _stop_tap(self) -> None:
        tap, self._tap = self._tap, None
        if tap:
            tap.stop()

    def _stage(self, phase: str, key: str) -> None:
        label = STAGE_LABELS.get(phase, {}).get(key, key)
        self._emit("stage", phase=phase, key=key, label=label)
        self._set(busy=label)

    def _step(self, key: str) -> None:
        self._set(busy=_TURN_STEPS.get(key, key))

    def _retry(self, agent, attempt, wait, reason) -> None:
        self._emit("retry", agent=agent, attempt=attempt,
                   of=getattr(self.lc.backend, "retries", None), wait=int(wait),
                   reason=str(reason))

    def _context(self) -> None:
        def read():
            try:
                cu = self.lc.game.context_usage()
            except Exception:  # noqa: BLE001 — a readout, never worth surfacing
                return
            if cu:
                self._emit("context", tokens=cu.tokens, limit=cu.context_limit, pct=cu.pct)
        self._spawn(read)

    def _status(self) -> None:
        try:
            st = asdict(self.lc.status())
        except Exception as e:  # noqa: BLE001
            self._error("status", e)
            return
        st["root"] = str(st["root"])
        self._emit("status", **st)

    # -- commands ------------------------------------------------------------

    def _input(self, text: str) -> None:
        awaiting = self.awaiting
        if awaiting == "confirm":
            self._reaction = text or None
            if text:
                self._say("player", text)
            self._set(awaiting=None, busy="the fight plays out")
            self._gate.set()
            return
        if not text:
            self._emit("error", what="input", message="empty")
            return
        if awaiting == "answer":
            self._say("player", text)
            self._set(awaiting=None, busy="the DM is thinking")
            self._spawn(self._setup_turn, text)
        else:  # turn or pc_action: the loop is parked on the keyboard source
            self._set(awaiting=None, busy="the DM is thinking")
            self._source.submit(text)

    def _meta(self, text: str) -> None:
        if not text:
            self._emit("error", what="meta", message="empty")
            return
        self._say("player", text, meta=True)
        self._set(awaiting=None, busy="the DM is answering")
        self._spawn(self._ask_meta, text)

    def _advance(self) -> None:
        if self.phase == "setup_done":
            self._spawn(self._plan_first)
        elif self.phase == "ready":
            self._spawn(self._open_session)
        elif self.phase == "complete":
            self._spawn(self._wrap)
        elif self._loop_live:
            # The loop still owns the game — take it down and let its exit run the wrap.
            self._after_loop = "wrap"
            if self.busy:
                self._notice("wrapping once this turn finishes", "rule")
            self._release_loop()
            self._set(awaiting=None)
        else:
            self._spawn(self._wrap)

    # -- setup -----------------------------------------------------------------

    def _open_setup(self) -> None:
        self._set(phase="setup", busy="the DM is thinking")
        self._activity_seen.clear()
        self._tap = self.lc.setup_stream(self._stream, on_tool=self._setup_activity)
        self.lc.setup.on_stage = lambda key: self._stage("setup", key)
        try:
            st = self.lc.setup.start()
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._error("opening setup", e)
            self._set(busy=None)
            return
        self._say("dm", st.reply)
        if st.done:
            self._setup_done()
        else:
            self._set(awaiting="answer", busy=None)

    def _setup_turn(self, text: str) -> None:
        try:
            st = self.lc.setup.turn(text)
        except Exception as e:  # noqa: BLE001
            self._error("the setup exchange", e)
            self._set(awaiting="answer", busy=None)
            return
        self._say("dm", st.reply)
        if st.done:
            self._setup_done()
        else:
            self._set(awaiting="answer", busy=None)

    def _setup_activity(self, name: str, arg: str) -> None:
        """Each label shows at most once: the DM touches files across categories in no fixed
        order, so without this the progress would flip-flop between the same few labels."""
        label = next((lbl for frag, lbl in _SETUP_ACTIVITY if frag in arg), None)
        if label and label not in self._activity_seen:
            self._activity_seen.add(label)
            self._emit("progress", label=label)

    def _setup_done(self) -> None:
        self._stop_tap()
        self._notice("the campaign is built", "success")
        self._set(phase="setup_done", awaiting=None, busy=None)

    def _plan_first(self) -> None:
        self._set(phase="planning", busy="planning session 1")
        try:
            n = self.lc.finish_setup(on_stage=lambda key: self._stage("setup", key),
                                     stream=self._stream)
        except Exception as e:  # noqa: BLE001
            self._error("planning session 1", e)
            self._set(phase="setup_done", busy=None)
            return
        self._notice(f"campaign ready · opening session {n}", "success")
        self._open_session()

    # -- play ------------------------------------------------------------------

    def _open_session(self) -> None:
        """Resume the session in progress if there is one, else open a fresh scene; then run
        the session loop on this thread until it returns."""
        game = self.lc.game
        game.on_step = self._step
        self._turn = 0
        self._set(phase="play", awaiting=None, busy="the DM sets the scene")
        self._tap = self.lc.play_stream(self._stream)
        try:
            scene = game.resume()
            resumed = scene is not None
            if not resumed:
                scene = game.start().final
        except BackendCancelled:
            self._stop_tap()
            self._notice("cancelled", "rule")
            self._set(phase="ready", busy=None)
            return
        except Exception as e:  # noqa: BLE001
            self._stop_tap()
            self._error("opening the session", e)
            self._set(phase="ready", busy=None)
            return
        if resumed:
            self._notice("resuming the session in progress")
        self._say("dm", scene)
        if game.in_combat:
            # Resumed straight into a live fight: the loop enters combat on its first pass.
            self._notice("resuming mid-fight — initiative", "rule")
        self._context()
        self._run_loop(scene)

    def _run_loop(self, scene: str) -> None:
        with self._lock:
            if self._closing:
                return
            self._source = self.lc.player_source()
            self._loop_live = True
        try:
            result = play_session(self.lc.game, self._source, scene, hooks=self._hooks(),
                                  turn_cap=self._turn_cap)
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self._loop_live = False
                self._stop_tap()
                self._error("the session", e)
                self._set(awaiting=None, busy=None)
            return
        with self._lock:
            self._loop_live = False
            self._stop_tap()
            after, self._after_loop = self._after_loop, None
            if self._closing:
                return
            if result.outcome == "complete":
                self._notice("the session has reached its end", "rule")
                self._set(phase="complete", awaiting=None, busy=None)
            elif result.outcome == "cap":
                self._notice(f"turn cap ({self._turn_cap}) reached — the session is still "
                             f"open", "rule")
                self._set(awaiting=None, busy=None)
        if result.outcome == "stopped" and after == "wrap":
            self._wrap()

    def _release_loop(self) -> None:
        """Release both places the loop can park: the player source and the confirm gate."""
        if self._source is not None:
            self._source.stop()
        self._reaction = None
        self._gate.set()

    def _hooks(self) -> PlayHooks:
        return PlayHooks(on_prompt=self._on_prompt, on_player=self._on_player,
                         on_turn=self._on_turn, on_slot=self._on_slot, on_beat=self._on_beat,
                         on_combat_end=self._on_combat_end, on_interrupt=self._on_interrupt)

    def _waiting_on_player(self, awaiting: str) -> None:
        if self._source.human:
            self._set(awaiting=awaiting, busy=None)
        else:
            self._set(awaiting=None, busy="the player is thinking")

    def _on_prompt(self, turns: int) -> None:
        self._waiting_on_player("turn")

    def _on_player(self, text: str, turns: int) -> None:
        self._say("player", text)
        self._set(awaiting=None, busy="the DM is thinking")

    def _on_turn(self, tr) -> None:
        self._turn += 1
        self._say("dm", tr.final)
        self._emit("turn", n=self._turn, tools=sorted(tr.tools))
        if tr.combat_started:
            self._notice("initiative! the fight begins", "rule")
        self._set()
        self._context()

    def _on_slot(self, event, turns: int) -> None:
        self._notice(f"your turn (round {event.round})", "rule")
        self._waiting_on_player("pc_action")

    def _on_beat(self, narration: str, who: str):
        """A resolved combat beat. For an NPC beat with a human player, park on the confirm
        gate and return the reaction (None confirms)."""
        self._say("dm", narration, combatant=who)
        with self._lock:
            if who == "pc" or not self._source.human or self._closing:
                return None
            self._reaction = None
            self._gate.clear()
            self._set(awaiting="confirm", busy=None)
        self._gate.wait()  # released by an input, or by close/advance
        return self._reaction

    def _on_combat_end(self, narration: str) -> None:
        self._notice("the fight is over — back to the table", "rule")
        self._say("dm", narration)
        self._set()
        self._context()

    def _on_interrupt(self, stage: str, exc: Exception, message: str) -> bool:
        """A model call raised. The session survives everything except a hard failure in a
        fight: out of combat the loop's next act is to ask the player, but re-entering a
        fight goes straight back to the model. Reverting the runner only applies to the
        stages that left a message in its context."""
        cancelled = isinstance(exc, BackendCancelled)
        if stage == "combat" and not cancelled:
            return False
        if stage in ("turn", "combat"):
            self.lc.game.revert_last_turn()
        if not cancelled:
            self._error("the turn", exc)
            self._set(busy=None)
        elif stage == "combat":
            # The resume guard rolled the in-flight tracker action back; the loop re-enters
            # the fight and re-resolves the interrupted combatant.
            self._notice("combat action cancelled", "rule")
            self._set(busy="the fight plays out")
        elif stage == "turn" and self._source.human:
            self._emit("handback", text=message)
            self._set(busy=None)
        else:
            self._notice("cancelled — asking again from the same scene", "rule")
            self._set(busy=None)
        return not self._closing

    def _ask_meta(self, question: str) -> None:
        """An out-of-game question while the loop idles on the player."""
        try:
            answer = self.lc.game.meta(question)
        except BackendCancelled:
            self.lc.game.revert_last_turn()
            self._emit("handback", text=question)
            self._set(awaiting="turn", busy=None)
            return
        except Exception as e:  # noqa: BLE001
            self._error("the question", e)
            self._set(awaiting="turn", busy=None)
            return
        self._say("dm", answer, meta=True)
        self._set(awaiting="turn", busy=None)
        self._context()

    # -- wrap ------------------------------------------------------------------

    def _wrap(self) -> None:
        self._set(phase="wrapping", awaiting=None, busy="wrapping the session")
        self._notice("wrapping the session", "rule")
        try:
            n = self.lc.wrap(on_stage=lambda key: self._stage("wrap", key), stream=self._stream)
        except Exception as e:  # noqa: BLE001
            self._error("the wrap", e)
            self._set(phase="complete", busy=None)
            return
        self._notice(f"session {n} planned and ready to start", "rule")
        self._set(phase="ready", busy=None)


def open_engine(directory: str | Path, *, player: str = "human", model=None, variant=None,
                port: int = 4181, turn_cap: int | None = None, mock: bool = False,
                setup: bool = False) -> Engine:
    """An engine over a real backend rooted at `directory`, or over `MockLifecycle`
    (`setup` starts the mock in its setup phase)."""
    if mock:
        from ..orchestrator.mock import MockLifecycle
        return Engine(MockLifecycle(start_in_setup=setup), directory="(mock)")

    from ..orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
    from ..orchestrator.backend import agent_overrides
    from ..orchestrator.logs import debug_enabled

    directory = Path(directory).resolve()
    logs = Logs.under(project=directory, debug=debug_enabled())
    backend = Backend(str(directory), port=port, logs=logs,
                      agents=agent_overrides(directory, model, variant)).start()
    try:
        gate = Gate(backend, CanonPreloader(str(directory)), logs=logs)
        lifecycle = Lifecycle(backend, gate, str(directory), logs=logs, player=player)
    except Exception:
        backend.stop()
        raise
    return Engine(lifecycle, cleanup=backend.stop, turn_cap=turn_cap,
                  directory=str(directory))
