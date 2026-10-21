"""
PlayApp — the rich-TUI front-end over the orchestrator `Game`.

Layout: a scene pane (the play — DM narration + your lines, one selectable
block per beat), a behind-the-screen pane (live model stream + per-turn tool
summary), a status bar (what the table is doing right now), a phase prompt
bar (yes/no at phase boundaries), and an input that switches between ACTION
mode (a turn) and META mode (an out-of-game question).

The scene pane mounts one widget per beat (see tui/widgets.py) into a
`VerticalScroll`, capped at `_SCENE_MAX_BLOCKS` — the full transcript is
always on disk at `campaign/sessions/{N}/transcript.md`. The
behind-the-screen pane is a `RichLog` — append-efficient, but not
text-selectable; the full turn log is on disk under the project's log dir
(`.opencode/logs/orchestrator-checks.log`).

Play is `orchestrator.play_session`, run once per session on a worker thread
(`_session_worker`) with a `PlayerSource` from the lifecycle. The keyboard source
parks that thread until `on_input_submitted` hands it a line, so this app is a set
of `PlayHooks` over the same loop `bench run` uses — which is what lets
`--player auto` be watched here (the source changes, nothing else does).

Model calls block, so they run off the UI thread (`asyncio.to_thread`). While
the table works, the input stays live for drafting (submits are held with a
notice), and three signals keep the app from going silent for minutes:

  - **Status bar:** the current phase (per-turn steps via `Game.on_step`,
    pipeline stages via `on_stage`), the trail of phases passed, an elapsed
    clock, and transient backend-retry notices.
  - **Pending block:** a "the DM is thinking" stand-in sits in the scene until
    the narration lands.
  - **Live stream:** an `EventTap` routes live model output (tokens + tool
    calls) into the behind-the-screen pane during every phase. The pane stays
    closed by default; open it with ctrl+g (it accumulates, so opening
    mid-turn reveals everything so far).

Phase boundaries ask instead of auto-chaining: when the runner ends a session
(or setup reports done), the prompt bar offers the next phase — Y runs it, N
leaves it available via ctrl+w or the Esc menu. The Esc menu is the mouse-and-
arrow surface over the same actions the keybinds and slash-commands drive.

The app talks only to a Lifecycle-like object (`game.start/turn/meta` →
`TurnResult`, `wrap`, `finish_setup`, `status`), so the same UI runs against
`MockLifecycle` or the real backend.

**Batch mode** (`batch=`, from `bench run --ui tui`) is the one thing that breaks the
one-campaign-per-app assumption everything above rests on: a batch is N run dirs, so the
lifecycle is *attached per run* rather than handed in at construction (`self.lc` is None
between runs, and `phase` answers for it). The batch itself stays above the app — it runs on
its own thread and calls back through `bench.runner.BatchHooks` — because per-run backends,
conditions stamping and the manifest are none of them per-session. What the app adds is the
chrome a batch needs and a session never did: `BatchHeader` (run k of N, outcome so far).

Watching is **read-only**: nothing typed reaches a run, ctrl+w is refused (a run wraps
itself), and even the context-usage readout is skipped — a watched run must make the same
calls in the same order as a headless one, or the archives stop pooling
(design/frontends.md § Constraints). The single exception is ctrl+x, whose meaning carries
over verbatim from a live session — abort the call in flight, the loop asks again from the
same scene — because a cancelled turn provably leaves no trace behind it.
"""

from __future__ import annotations

import asyncio
import random
import re
import threading

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, RichLog

from gm_llm.orchestrator.backend import BackendCancelled
from gm_llm.orchestrator.play import PlayHooks, play_session
from gm_llm.orchestrator.textmarkup import inline

from .screens import MenuScreen, RollScreen, StatusScreen
from .widgets import (
    BatchHeader, DMBlock, PendingBlock, PlayerLine, PromptBar, SceneLine, StatusBar,
)


class PlayApp(App):
    CSS = """
    #main   { height: 1fr; }
    #scene  { width: 2fr; border: round $primary;   padding: 0 1; }
    #screen { width: 1fr; border: round $secondary; }
    #screen.hidden { display: none; }
    #cmd { height: 3; border: tall $accent; }
    """

    BINDINGS = [
        ("escape", "menu", "Menu"),
        ("ctrl+g", "toggle_screen", "Behind-screen"),
        ("ctrl+t", "toggle_mode", "Action/Meta"),
        # priority: the input keeps focus while the table works (drafting), and
        # Input binds ctrl+x (cut) / ctrl+w (delete word) itself — these must
        # reach the app regardless.
        Binding("ctrl+x", "cancel", "Cancel turn", priority=True),
        Binding("ctrl+w", "wrap", "Wrap session", priority=True),
        ("ctrl+q", "quit", "Quit"),
    ]

    # Cap the scene pane's mounted blocks so layout stays cheap as the session
    # grows. The full transcript is always on disk — this is just the visible
    # scrollback. Once the cap is hit, the oldest blocks are removed and a
    # marker is mounted at the top so the truncation is visible.
    _SCENE_MAX_BLOCKS = 200

    # Spoiler-free labels for the per-turn steps `Game.on_step` announces.
    TURN_STEPS = {
        "draft": "the DM is writing",
        "done": "finishing up",
    }

    def __init__(self, lifecycle=None, cleanup=None, theme: str = "dracula",
                 turn_cap: int | None = None, batch=None):
        super().__init__()
        self.lc = lifecycle
        self.cleanup = cleanup
        self._theme = theme
        self.mode = "action"
        self._turn = 0
        self._working = False        # a worker owns the table; submits are held
        self._wrapping = False
        self._pending = None         # phase action awaiting a yes: "wrap" | "finish_setup" | "open"
        self._thinking = None        # the PendingBlock in the scene, while a call is in flight
        self._setup_tap = None       # EventTap streaming setup authoring behind the screen
        self._setup_stages_seen = set()  # spoiler-free setup stages already shown (each shows once)
        self._ctx_note = ""          # " · ctx 39% (78k/200k)" — refreshed after each turn
        # The session loop (orchestrator.play_session), run on a worker thread for the life
        # of one session: `_source` is where it takes player messages from (a KeyboardPlayer
        # fed by on_input_submitted, or an AgentPlayer for `--player auto`), `_loop_live` says
        # whether a submit has anywhere to go, and `_after_session` is a phase action queued
        # behind the loop's exit (a wrap can't run while the loop still owns the game).
        self._source = None
        self._loop_live = False
        self._after_session = None
        self._turn_cap = turn_cap    # only `--player auto` caps; a human plays uncapped
        self._session_tap = None     # EventTap streaming the whole session behind the screen
        # Combat: the loop hands fights to `play_combat`, which drives them through the
        # CombatDriver — the app only renders beats and answers the confirm gate.
        # `_combat_awaiting` is what the input box is currently for ("pc" = the PC's slot,
        # "confirm" = an NPC beat awaiting the player's Enter-or-react); `_combat_gate` /
        # `_combat_reaction` hand the confirm-gate answer from the UI thread back to the
        # loop worker blocked in `_on_combat_beat`.
        self._combat_awaiting = None
        self._combat_gate = threading.Event()
        self._combat_reaction = None
        # Batch mode: `batch(hooks)` plays N runs (bench's `run_batch`) on its own thread,
        # attaching a lifecycle per run. None for every other mode — one campaign, handed in.
        self._batch = batch
        self._batch_thread = None

    @property
    def game(self):
        """The session currently in play; the lifecycle swaps it on wrap. None in batch
        mode between runs, when no lifecycle is attached."""
        return self.lc.game if self.lc is not None else None

    @property
    def phase(self) -> str:
        """Where the campaign stands — asked of the lifecycle, which a batch app doesn't
        have between runs. Nothing but a real campaign is ever in setup, so "play" is the
        honest answer for an unattached app: no setup affordance, no wrap prompt."""
        return self.lc.phase if self.lc is not None else "play"

    def compose(self) -> ComposeResult:
        yield Header()
        yield BatchHeader()
        with Horizontal(id="main"):
            yield VerticalScroll(id="scene")
            # RichLog: append-efficient (no O(n²) re-render), handles its own
            # scrolling, parses console markup (so EventTap's markup dialect
            # renders coloured). Not text-selectable — the full turn log is on
            # disk under the project's .opencode/logs/.
            # min_width=0 overrides RichLog's default of 78 columns, which
            # otherwise forces the pane wider than its 1fr layout slot and
            # produces a horizontal scrollbar (wrapping at 78, not at the
            # pane's actual width).
            yield RichLog(id="screen", markup=True, wrap=True, auto_scroll=False,
                          min_width=0, classes="hidden")
        yield StatusBar()
        yield PromptBar()
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = self._theme if self._theme in self.available_themes else "dracula"
        self._status = self.query_one(StatusBar)
        self._prompt = self.query_one(PromptBar)
        self._header = self.query_one(BatchHeader)
        self._write_screen("[b]behind the screen[/b] — live model stream · tools per turn")
        if self._batch is not None:
            # Watching a batch: no player affordances to advertise, and the retry notice is
            # wired per run (each run boots its own backend).
            self._scene_status("esc menu · ctrl+g behind-screen · ctrl+x cancel the call "
                               "in flight · ctrl+q stop the batch")
            self._start_batch()
            return
        # Backend retries surface as a *sticky* status-bar warning (with the running
        # clock), so a rate-limited hang stays visibly flagged the whole time it retries
        # instead of looking like a silent hang. It clears when a call finally gets through.
        self._scene_status("esc menu · ctrl+t action/meta · ctrl+g behind-screen · "
                           "ctrl+x cancel · ctrl+w wrap · /roll 2d6+3 · /meta <q> · /quit")
        self._wire_retry_notice(self.lc.backend)
        self._sync_input()
        self._refresh_subtitle()
        if self.phase == "wrap_pending":
            # A prior run ended session N (task_complete fired) and the player
            # never confirmed the wrap — show the same choice again, no model
            # call, no resume: reconcile-and-prep or quit, nothing else.
            self._show_wrap_pending()
            return
        self.run_worker(self._open(), exclusive=True)

    def _wire_retry_notice(self, backend) -> None:
        """Route a backend's retry ladder to the status bar. One backend per app normally;
        one per run in batch mode, which is why this is a method and not a line in on_mount."""
        backend.on_retry = lambda agent, attempt, wait, reason: self._ui(
            self._status.note,
            f"{agent} call failed ({escape(str(reason))}) — "
            f"retry {attempt}/{getattr(backend, 'retries', '?')} in {int(wait)}s", True)

    def _show_wrap_pending(self) -> None:
        self._pending = "wrap"
        self._sync_input()
        self._scene_status(f"— session {self.lc.session} complete — reconcile & prep "
                           f"session {self.lc.session + 1}, or quit and decide later —",
                           kind="rule")
        self._prompt.ask(f"Session {self.lc.session} complete — "
                         f"reconcile & prep session {self.lc.session + 1}?")

    # -- scene pane (one widget per beat) ------------------------------------

    def _scene_mount(self, widget) -> None:
        """Mount a block into the scene, trim past the cap, and auto-follow
        only when the view is already pinned to the bottom — a reader scrolled
        up to read back isn't yanked down by the next beat."""
        scene = self.query_one("#scene", VerticalScroll)
        pinned = scene.scroll_offset.y >= scene.max_scroll_y - 2
        scene.mount(widget)
        blocks = [w for w in scene.children if not w.has_class("truncated")]
        excess = len(blocks) - self._SCENE_MAX_BLOCKS
        if excess > 0:
            for w in blocks[:excess]:
                w.remove()
            if not scene.query(".truncated"):
                scene.mount(SceneLine("… older beats truncated — full transcript in "
                                      "campaign/sessions/ …", classes="truncated"),
                            before=0)
        if pinned:
            # scroll after the mount has laid out, or max_scroll_y is stale
            self.call_after_refresh(lambda: scene.scroll_end(animate=False))

    def _scene_status(self, text: str, kind: str = "status") -> None:
        self._scene_mount(SceneLine(text, kind=kind))

    def _scene_player(self, markup_text: str, meta: bool = False) -> None:
        self._scene_mount(PlayerLine(markup_text, meta=meta))

    def _scene_dm(self, markup_text: str, meta: bool = False) -> DMBlock:
        block = DMBlock(markup_text, meta=meta)
        self._scene_mount(block)
        return block

    def _scene_thinking(self, label: str = "the DM is thinking") -> None:
        self._clear_thinking()
        self._thinking = PendingBlock(label)
        self._scene_mount(self._thinking)

    def _clear_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.remove()
            self._thinking = None

    # -- behind-the-screen pane ----------------------------------------------

    def _write_screen(self, markup: str) -> None:
        self._append_screen(markup + "\n")

    def _append_screen(self, text: str) -> None:
        """Screen pane: a RichLog. Each chunk is written as a single renderable
        so console markup — including tags that span newlines, like the headings
        and tool-call lines EventTap emits — parses correctly. Auto-follows only
        when pinned to the bottom, so a reader scrolled up isn't yanked down."""
        if not text:
            return
        log = self.query_one("#screen", RichLog)
        follow = log.scroll_offset.y >= log.max_scroll_y - 2
        log.write(text, scroll_end=follow)

    # -- input mode & busy state ----------------------------------------------

    def _sync_input(self) -> None:
        inp = self.query_one("#cmd", Input)
        if self._batch is not None:
            # A watched batch is read-only — the box is kept only for /quit and /roll.
            inp.border_title = "WATCHING — a bench batch plays itself"
            inp.placeholder = "nothing typed reaches the run · ctrl+q stops the batch"
            return
        if self._combat_awaiting == "confirm":
            inp.border_title = "COMBAT — Enter to confirm, or type a reaction"
            inp.placeholder = "Enter to confirm the enemy's action · type a reaction to interject"
            return
        if self._combat_awaiting == "pc":
            inp.border_title = "COMBAT — your turn"
            inp.placeholder = "What does your character do this turn?"
            return
        if self._working:
            inp.border_title = "…thinking — draft freely, send once the table frees up…"
        elif self.phase == "setup":
            inp.border_title = "SETUP — talk to the DM"
        elif self._pending == "wrap":
            inp.border_title = "SESSION COMPLETE — reconcile or quit, nothing else"
        elif self._pending == "open":
            inp.border_title = "SESSION READY — start it, or quit"
        elif self.mode == "action":
            inp.border_title = "ACTION"
        else:
            inp.border_title = "META — out-of-game"
        inp.placeholder = ("Answer the DM…" if self.phase == "setup"
                           else "Y to wrap, N not yet, or /quit" if self._pending == "wrap"
                           else "Y to start the session, N not yet, or /quit" if self._pending == "open"
                           else "What does your character do?" if self.mode == "action"
                           else "Ask the DM a logistical question…")

    def _default_busy_label(self) -> str:
        if self._batch is not None:
            return "the run is playing"
        if self.phase == "setup":
            return "the DM is building"
        if self._wrapping:
            return "wrapping the session"
        return "the table is thinking"

    def _busy(self, busy: bool, label: str | None = None) -> None:
        """The single busy choke point: flips `_working` (submits held, cancel
        armed) and starts/stops the status bar. The input itself stays enabled
        so the player can draft the next message during a long call."""
        self._working = busy
        self._sync_input()
        if busy:
            self._status.start(label or self._default_busy_label())
        else:
            self._status.stop()
            self._refresh_subtitle()
            self.query_one("#cmd", Input).focus()

    def _turn_step(self, key: str) -> None:
        self._status.set_phase(self.TURN_STEPS.get(key, key))

    def _refresh_subtitle(self) -> None:
        base = "SETUP" if self.phase == "setup" else f"{self.mode.upper()} mode"
        self.sub_title = base + self._ctx_note

    def _spawn_context_refresh(self) -> None:
        """Kick off a background refresh of the context-usage note (a couple of
        HTTP round-trips) — fire-and-forget, doesn't hold up the input.

        Never in batch mode: a watched run has to hit the backend in the same order a
        headless one does, and a per-turn readout the archive can't see is exactly the kind
        of frontend side-effect the comparability invariant rules out."""
        if self._batch is None and self.phase == "play":
            self.run_worker(self._refresh_context_note(), exclusive=False)

    async def _refresh_context_note(self) -> None:
        try:
            cu = await asyncio.to_thread(self.game.context_usage)
        except Exception:  # noqa: BLE001 — a status readout, never worth surfacing
            cu = None
        # Denominator is the full window (the hard wall), not the wrap threshold, so the
        # readout stays under 100% while tokens climb past the threshold during the wrap
        # countdown; pct is measured against the same window, so fraction and percent agree.
        self._ctx_note = (f" · ctx {cu.pct:.0f}% ({cu.tokens / 1000:.0f}k/{cu.context_limit / 1000:.0f}k)"
                          if cu else "")
        self._refresh_subtitle()

    # -- play stream (live model output → behind-the-screen pane) -----------

    def _start_stream(self):
        """Start an EventTap routing live model output (streaming tokens + tool
        calls) into the behind-the-screen pane. The pane stays closed by
        default — toggle it with ctrl+g to watch. Returns the tap (or None);
        the caller stops it when the blocking call returns."""
        stream = lambda s: self.call_from_thread(self._append_screen, s)
        return self.lc.play_stream(stream)

    # -- game interaction (off the UI thread) -------------------------------

    async def _open(self) -> None:
        self._busy(True)
        if self.phase == "setup":
            await self._open_setup()   # _open_setup starts its own stream
            return
        # (Re)wire the per-turn step ticker — the lifecycle swaps the game on
        # every phase roll, and _open always follows.
        self.game.on_step = lambda k: self.call_from_thread(self._turn_step, k)
        self._scene_thinking("the DM sets the scene")
        tap = self._start_stream()
        try:
            # Resume an in-progress session (preserves its transcript) if there is one;
            # otherwise open a fresh scene. After a wrap, N+1 has no transcript → fresh.
            scene = await asyncio.to_thread(self.game.resume)
            resumed = scene is not None
            if not resumed:
                scene = (await asyncio.to_thread(self.game.start)).final
        except BackendCancelled:
            self._cancelled_note()
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("opening the session", e)
            return
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread, same
            # pattern as _finish_setup.
            if tap:
                await asyncio.to_thread(tap.stop)
        self._clear_thinking()
        if resumed:
            self._scene_status("— resuming the session in progress —")
        self._scene_dm(inline(scene))
        if self.game.in_combat:
            # Resumed straight into a live fight (the tracker state file survived): the loop
            # enters combat on its first pass, so this is only the sign-post.
            self._scene_status("— resuming mid-fight — initiative —", kind="rule")
        self._spawn_context_refresh()
        self._start_session(scene)

    # -- the session loop (one per session, on a worker thread) --------------
    #
    # `play_session` is the one turn loop (orchestrator/play.py); this app is a set of
    # hooks over it. The loop blocks — on a model call, or on the keyboard source waiting
    # for the player — so it lives on a worker thread and every hook that touches the
    # screen hops back with `call_from_thread`. The two hooks that DON'T are deliberate:
    # `on_beat` blocks the worker on the combat confirm gate, and `on_interrupt` reverts
    # the runner session (a backend call) before touching the UI.

    def _start_session(self, scene: str) -> None:
        """Open the session loop over the current game, with a fresh player source."""
        self._source = self.lc.player_source()
        self._loop_live = True
        # Its own worker group: the ad-hoc `exclusive=True` workers (a meta question, the
        # status modal) must not cancel the loop that owns the session.
        self.run_worker(self._session_worker(scene), group="session", exclusive=True)

    def _ui(self, fn, *args) -> None:
        """Hop to the UI thread from the loop's worker — and no-op once the app has stopped.
        `call_from_thread` parks the calling thread until the app's event loop runs the
        callback, so a hook that fires during shutdown would park a pool thread forever, and
        a parked pool thread keeps the interpreter from exiting."""
        if not self.is_running:
            return
        try:
            self.call_from_thread(fn, *args)
        except RuntimeError:
            pass  # the app stopped between the check and the call

    def _session_hooks(self) -> PlayHooks:
        ui = self._ui
        return PlayHooks(
            on_prompt=lambda turns: ui(self._await_player),
            on_player=lambda text, turns: ui(self._player_said, text),
            on_turn=lambda tr: ui(self._render_turn, tr),
            on_slot=lambda event, turns: ui(self._await_pc_slot, event),
            on_beat=self._on_combat_beat,       # worker thread: renders, then blocks for confirm
            on_combat_end=lambda narration: ui(self._combat_ended, narration),
            on_interrupt=self._on_interrupt,    # worker thread: reverts, then renders
        )

    async def _session_worker(self, scene: str) -> None:
        # One tap for the whole session (the same shape `bench run --stream` uses), so the
        # pane keeps streaming across turns, fights and meta questions without restarting.
        self._session_tap = self._start_stream()
        try:
            result = await asyncio.to_thread(
                play_session, self.game, self._source, scene,
                hooks=self._session_hooks(), turn_cap=self._turn_cap)
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("the session", e)
            return
        finally:
            self._loop_live = False
            if self._session_tap:
                # stop() flushes buffered stream content through the write callback
                # (which uses call_from_thread) — must run off the app thread.
                await asyncio.to_thread(self._session_tap.stop)
                self._session_tap = None
        self._session_done(result)

    def _session_done(self, result) -> None:
        """The loop returned. `complete` offers the wrap; `stopped` means the app took the
        loop down itself and may have queued the action it took it down *for*; `cap` can only
        happen under `--player auto`, which is watched, not driven."""
        self._combat_awaiting = None
        self._busy(False)
        if result.outcome == "complete":
            # The runner signalled the session's end — offer the wrap (reconcile + prep
            # N+1) instead of auto-running minutes of pipeline.
            self._scene_status("— the session has reached its end —", kind="rule")
            self._pending = "wrap"
            self._prompt.ask(f"Session {self.lc.session} complete — "
                             f"reconcile & prep session {self.lc.session + 1}?")
            return
        if result.outcome == "cap":
            self._scene_status(f"— turn cap ({self._turn_cap}) reached — the session is "
                               f"still open —", kind="rule")
            return
        queued, self._after_session = self._after_session, None
        if queued == "wrap":
            self.run_worker(self._do_wrap(), exclusive=True)

    def _stop_session(self, then: str | None = None) -> bool:
        """Take the loop down (queueing `then` for when it lands) and say whether it was
        still running. Nothing that reaches for the game — a wrap, quitting — may run while
        the loop still owns it.

        Both places the worker can *park* are released, not just the live-looking one: the
        player source, and combat's confirm gate. On the way out Textual cancels the worker's
        coroutine while its thread keeps running, so `_loop_live` can already be False with a
        thread still parked — and a parked pool thread keeps the interpreter from exiting."""
        live = self._loop_live
        self._after_session = then if live else None
        if self._source is not None:
            self._source.stop()
        self._combat_reaction = None
        self._combat_gate.set()
        return live

    # -- batch mode: N runs, one app (bench run --ui tui) --------------------
    #
    # The batch runs on its own thread and attaches a lifecycle per run; the app renders
    # what it is handed and never drives it. Everything below the `on_open` handoff is the
    # ordinary session machinery — the loop, the hooks, the stream tap — which is the whole
    # point of frontends steps 1–3: rendering a bench run costs a lifecycle swap, not a
    # second app.

    def _start_batch(self) -> None:
        self._header.activate()
        self._busy(True, label="preparing the batch")
        self._batch_thread = threading.Thread(target=self._run_batch, name="bench-batch")
        self._batch_thread.start()

    def _run_batch(self) -> None:
        """The batch, off the UI thread for the app's whole life.

        Deliberately a plain thread and not a Textual worker: the CLI joins it *after* the
        app comes down, so a run in flight finishes unwinding — backend stopped, manifest
        line written — instead of being abandoned mid-record when the screen closes."""
        from gm_llm.bench.runner import BatchHooks
        hooks = BatchHooks(
            on_run=lambda i, n, run_id: self._ui(self._batch_run, i, n, run_id),
            on_open=self._batch_open,          # worker thread: attaches, returns the hooks
            on_stage=lambda key: self._ui(self._batch_stage, key),
            on_close=self._batch_close)        # worker thread: stops the tap, then renders
        try:
            self._batch(hooks)
        except Exception as e:  # noqa: BLE001 — surface any failure into the scene
            self._ui(self._phase_failed, "the batch", e)
            return
        self._ui(self._batch_done)

    def batch_running(self) -> bool:
        return self._batch_thread is not None and self._batch_thread.is_alive()

    def join_batch(self, timeout: float | None = None) -> None:
        """Wait for the batch thread after `run()` returns — the caller's half of the
        unwind. A run whose model call is still in flight keeps this waiting until the
        call's own timeout gives up, which is the honest behaviour: its manifest line
        isn't written yet."""
        if self._batch_thread is not None:
            self._batch_thread.join(timeout)

    def note(self, msg: str) -> None:
        """A bench progress note (the `note` callback `run_batch` writes its log through).
        Behind the screen, not into the scene: the scene is the play."""
        self._ui(self._write_screen, f"[dim]\\[bench] {escape(msg)}[/]")

    def _batch_run(self, index: int, total: int, run_id: str) -> None:
        self._header.set_run(index, total, run_id)
        self._scene_status(f"── run {index}/{total} · {run_id} ──", kind="rule")
        self._busy(True, label="assembling the run")

    def _batch_open(self, lifecycle, source, scene: str):
        """`on_open`, on the batch thread: attach this run's lifecycle and hand back the
        hooks its turns render through. The source is the run's, not one built here — the
        loop is bench's, and two sources would mean two players."""
        self.lc = lifecycle
        self._source = source
        self._loop_live = True
        self._turn = 0
        self._wire_retry_notice(lifecycle.backend)
        if lifecycle.game is not None:
            lifecycle.game.on_step = lambda k: self._ui(self._turn_step, k)
        self._session_tap = lifecycle.play_stream(
            lambda s: self._ui(self._append_screen, s))
        self._ui(self._batch_opened, scene)
        return self._session_hooks()

    def _batch_opened(self, scene: str) -> None:
        self._clear_thinking()
        self._scene_dm(inline(scene))
        self._busy(True)

    def _batch_stage(self, key: str) -> None:
        """A post-wrap pipeline stage — the run reconciling itself, rendered with the same
        ticker a played campaign's wrap uses."""
        if not self._working:
            self._busy(True, label="wrapping the run")
        self._announce_stage("wrap", key)

    def _batch_close(self, record: dict) -> None:
        """`on_close`, on the batch thread. The tap is stopped here rather than on the UI
        thread: `stop()` flushes through a `call_from_thread` write callback."""
        self._loop_live = False
        tap, self._session_tap = self._session_tap, None
        if tap:
            tap.stop()
        self._ui(self._batch_closed, record)

    def _batch_closed(self, record: dict) -> None:
        outcome = str(record.get("outcome", "?"))
        self._clear_thinking()
        self.lc = None       # this run's backend is being stopped; nothing is attached now
        self._source = None
        self._busy(False)
        self._header.set_outcome(outcome)
        self._scene_status(f"— {record.get('run', 'run')}: {outcome} "
                           f"({record.get('turns', 0)} turn(s)) —",
                           kind="success" if outcome == "complete" else "error")

    def _batch_done(self) -> None:
        self._busy(False)
        self._header.set_done()
        self._scene_status("— the batch is done — ctrl+q to close —", kind="success")

    # -- setup: the new-campaign conversation (phase == "setup") ------------

    # Map a written file to a spoiler-free build stage (first match wins). The dm's
    # authoring otherwise looks frozen for minutes; this gives the scene a heartbeat
    # without leaking what's being written.
    _SETUP_STAGES = (
        ("characters/", "building your character"),
        ("arcs/", "shaping the story"),
        ("world/", "fleshing out the world"),
        ("documents/", "writing the in-world documents"),
        ("state/", "setting the opening scene"),
        ("INDEX", "organizing the campaign"),
        ("campaign.md", "organizing the campaign"),
    )

    def _setup_activity(self, name: str, arg: str) -> None:
        """A tool fired during setup — surface a coarse, spoiler-free stage in the scene
        the first time we see it, so the build shows progress instead of hanging silently.
        Each stage shows at most once: the dm touches files across categories in no fixed
        order, so without this the ticker flip-flops between the same few labels."""
        stage = next((label for frag, label in self._SETUP_STAGES if frag in arg), None)
        if stage and stage not in self._setup_stages_seen:
            self._setup_stages_seen.add(stage)
            self._scene_status(f"  ▸ {stage}…")

    async def _open_setup(self) -> None:
        """Open a brand-new campaign: a guided conversation in the scene pane, with the
        dm's authoring streamed behind the screen. The pane stays closed by default (as
        in every mode) so it doesn't compete with the conversation — ctrl+g to watch."""
        self._write_screen("\n[b]— building the campaign —[/b]\n")
        self._setup_stages_seen.clear()
        stream = lambda s: self.call_from_thread(self._append_screen, s)
        # tool calls drive a spoiler-free progress ticker in the scene (the full,
        # spoiler-bearing authoring stays behind the screen).
        activity = lambda name, arg: self.call_from_thread(self._setup_activity, name, arg)
        self._setup_tap = self.lc.setup_stream(stream, on_tool=activity)
        # Setup announces its stages over the same on_stage protocol as the wrap
        # pipeline; the tool-path ticker above stays as the fine-grained activity
        # feed *within* a long interactive stage.
        self.lc.setup.on_stage = lambda key: self.call_from_thread(
            self._announce_stage, "setup", key)
        try:
            st = await asyncio.to_thread(self.lc.setup.start)
        except BackendCancelled:
            self._cancelled_note()
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("opening setup", e)
            return
        self._scene_dm(inline(st.reply))
        if st.done:
            await self._setup_done()
        else:
            self._busy(False)

    async def _do_setup(self, text: str) -> None:
        self._busy(True)
        self._scene_thinking()
        try:
            st = await asyncio.to_thread(self.lc.setup.turn, text)
        except BackendCancelled:
            self._cancelled_note()
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("the setup exchange", e)
            return
        self._clear_thinking()
        self._scene_dm(inline(st.reply))
        if st.done:
            await self._setup_done()
        else:
            self._busy(False)

    async def _setup_done(self) -> None:
        """Setup reported done: stop borrowing the stream, then ask before the
        next phase (planning session 1) rather than auto-running it."""
        if self._setup_tap:
            # stop() flushes the tap's buffered line through the write callback
            # (call_from_thread) — so it must run off the app thread, not here.
            await asyncio.to_thread(self._setup_tap.stop)
            self._setup_tap = None
        self._scene_status("— the campaign is built —", kind="rule")
        self._busy(False)
        self._pending = "finish_setup"
        self._prompt.ask("Setup complete — plan & start session 1?")

    async def _finish_setup(self) -> None:
        """Plan session 1 (behind the screen), then open play(1). Runs when the
        player confirms the setup-done prompt (or triggers it from the menu)."""
        self._busy(True, label="planning session 1")
        self._scene_status("— planning session 1 —", kind="rule")
        self._write_screen("\n[b]— planning session 1 —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._announce_stage, "setup", key)
        stream = lambda s: self.call_from_thread(self._append_screen, s)
        try:
            n = await asyncio.to_thread(self.lc.finish_setup, ticker, stream)
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._scene_status(f"— setup failed: {escape(str(e))} —", kind="error")
            self._busy(False)
            return
        self._scene_status(f"— campaign ready · opening session {n} —", kind="success")
        self._turn = 0
        await self._open()  # phase is now "play" → opens session 1

    # -- input ----------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd":
            return  # a modal's input (e.g. the roll prompt), not the play bar
        text = event.value.strip()
        if self._batch is not None:
            # Watching a bench batch: read-only. Not a UX preference — a typed line would
            # be a turn (or a meta call) the archive can't distinguish from the run's own,
            # and the run would stop being comparable to a headless one. /quit and the
            # local dice roller are the two things that touch nothing.
            event.input.value = ""
            low = text.lower()
            if low in ("/quit", "/exit", "/q"):
                self.exit()
            elif low.startswith("/roll"):
                self._scene_status(roll_expr(text[5:].strip())
                                   or "could not parse — try /roll 2d6+3", kind="rule")
            elif text:
                self._scene_status("— watching a bench batch — nothing typed reaches the "
                                   "run · ctrl+q stops the batch —", kind="rule")
            return
        # Combat routing takes precedence: the confirm gate needs a bare Enter (an empty
        # submit) to mean "confirm", and combat input must reach the fight even while the
        # pump worker is mid-flight. `/roll` (local dice) and `/quit` still work here.
        if self._combat_awaiting in ("confirm", "pc"):
            event.input.value = ""
            low = text.lower()
            if low in ("/quit", "/exit", "/q"):
                self.exit()
                return
            if low.startswith("/roll"):
                result = roll_expr(text[5:].strip())
                self._scene_status(result or "could not parse — try /roll 2d6+3", kind="rule")
                return
            if self._combat_awaiting == "confirm":
                self._combat_resolve_confirm(text)  # empty = confirm; text = interject
            elif text:
                self._submit_player(text)
            return
        if not text:
            event.input.value = ""
            return
        # Drafting while the table works: the box stays live, but the send is
        # held (and kept) until the current call resolves.
        if self._working:
            self.notify("still thinking — your draft will keep", severity="warning", timeout=3)
            return
        event.input.value = ""

        if text.lower() in ("/quit", "/exit", "/q"):
            self.exit()
            return
        # During setup the bar is a plain answer to the DM — no play commands apply.
        if self.phase == "setup":
            self._prompt.dismiss()  # answering the DM supersedes a shown prompt
            self._scene_player(f"[$success bold]You[/]  {inline(text)}")
            self.run_worker(self._do_setup(text), exclusive=True)
            return
        # /wrap — end the session and run the post-session pipeline, then open the next.
        if text.lower() in ("/wrap", "/end"):
            self.action_wrap()
            return
        # /roll — a local dice helper; doesn't take a turn, just shows the result
        # so you can report it in your next action.
        if text.lower().startswith("/roll"):
            result = roll_expr(text[5:].strip())
            self._scene_status(result or "could not parse — try /roll 2d6+3", kind="rule")
            return
        # Session complete, awaiting wrap-or-quit — the only two choices. Block
        # everything else here so a stray message can't reach the already-ended
        # runner (that's how a level-up once ended up delivered days late, buried
        # in an unrelated reply, instead of at the actual close).
        if self._pending == "wrap":
            self._scene_status("— session complete — answer Y/N above, or /wrap · "
                               "/quit — nothing else reaches the table until then —",
                               kind="rule")
            return
        # Next session planned but not yet opened — answer Y/N to start it. The opening
        # scene is a model call (not a player turn), so a typed action can't begin it.
        if self._pending == "open":
            self._scene_status("— session ready — answer Y above to start it, or /quit —",
                               kind="rule")
            return
        # /meta — an out-of-game question without switching modes.
        if text.lower().startswith("/meta"):
            q = text[5:].strip()
            if q:
                self._prompt.dismiss()
                self._scene_player(f"You (out-of-game)  {escape(q)}", meta=True)
                self.run_worker(self._do_meta(q), exclusive=True)
            return

        self._prompt.dismiss()  # playing on past a phase prompt — it stays in the menu
        if self.mode == "action":
            self._submit_player(text)
        else:
            self._scene_player(f"You (out-of-game)  {escape(text)}", meta=True)
            self.run_worker(self._do_meta(text), exclusive=True)

    def _submit_player(self, text: str) -> None:
        """Hand a typed line to the session loop, which is parked on the keyboard source.
        The echo isn't here: `on_player` does it for both player kinds a beat later, which
        is also what closes the window on a second submit racing the first."""
        if not self._loop_live:
            self._scene_status("— the session loop has stopped — ctrl+w to wrap, or /quit —",
                               kind="rule")
            return
        if not self._source.human:
            # `--player auto`: the agent supplies the turns and the source has no inbox.
            self.notify("the player agent is driving this session — ctrl+w to stop it",
                        severity="warning", timeout=3)
            return
        self._combat_awaiting = None
        self._busy(True)
        self._source.submit(text)

    # -- the loop's hooks, on the UI thread ---------------------------------

    def _await_player(self) -> None:
        """The loop wants the next player message. A human gets the input box back; an agent
        player is a call in flight like any other, so the table stays busy."""
        self._combat_awaiting = None
        if self._source.human:
            self._clear_thinking()
            self._busy(False)
        else:
            self._busy(True, label="the player is thinking")
            self._scene_thinking("the player is thinking")

    def _player_said(self, text: str) -> None:
        """The player's message — echoed here for both sources, so a watched `--player auto`
        run reads exactly like a played one."""
        self._clear_thinking()
        label = "You" if self._source.human else "Player"
        self._scene_player(f"[$success bold]{label}[/]  {escape(text)}")
        self._busy(True)
        self._scene_thinking()

    def _render_turn(self, tr) -> None:
        self._clear_thinking()
        self._scene_dm(inline(tr.final))
        self._render_turn_detail(tr)
        self._spawn_context_refresh()
        if tr.combat_started:
            # The runner called start_encounter — the loop hands the fight to play_combat
            # on its next pass, and normal turns resume when it ends.
            self._scene_status("— initiative! the fight begins —", kind="rule")

    async def _do_meta(self, question: str) -> None:
        """An out-of-game question, asked while the loop idles on the player. No tap of its
        own: the session tap is already streaming this call behind the screen."""
        self._busy(True)
        self._scene_thinking("the DM is answering")
        try:
            answer = await asyncio.to_thread(self.game.meta, question)
        except BackendCancelled:
            await asyncio.to_thread(self.game.revert_last_turn)
            self._hand_back(question)
            self._busy(False)
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("the question", e)
            return
        self._clear_thinking()
        self._scene_dm(inline(answer), meta=True)
        self._busy(False)
        self._spawn_context_refresh()

    # -- combat mode (initiative-driven; the driver owns the policy) ----------
    #
    # A fight is `play_combat` inside the session loop, driven by the library's
    # `CombatDriver`: this app only renders beats, gets input, and answers the confirm
    # gate — no combat policy here. `_on_combat_beat` runs on the loop's worker thread; it
    # renders each beat and, for an NPC beat, blocks on `_combat_gate` until the player
    # confirms (Enter) or interjects (a typed reaction). See design/combat.md "The combat
    # loop".

    def _await_pc_slot(self, event) -> None:
        """The loop reached the PC's slot (`on_slot`). For a human that's the input box; an
        agent player's action is a call in flight, so the table stays busy."""
        self._clear_thinking()
        self._scene_status(f"— your turn (round {event.round}) —", kind="rule")
        if self._source.human:
            self._combat_awaiting = "pc"
            self._busy(False)
        else:
            self._busy(True, label="the player is thinking")
            self._scene_thinking("the player is thinking")

    def _combat_ended(self, narration: str) -> None:
        self._clear_thinking()
        self._combat_awaiting = None
        self._scene_status("— the fight is over — back to the table —", kind="rule")
        self._scene_dm(inline(narration))
        self._spawn_context_refresh()

    def _on_combat_beat(self, narration: str, who: str):
        """Driver callback, run on the loop's worker thread. Renders a beat; for an NPC beat
        it then blocks for the player's confirm-or-react and returns the reaction (or None
        to confirm). A PC beat is committed directly, and an agent player has no confirm to
        give — both render and return None (which confirms)."""
        self._ui(self._scene_combat_beat, narration, who)
        if who == "pc" or not self._source.human or not self.is_running:
            return None
        self._combat_reaction = None
        self._combat_gate.clear()
        self._ui(self._combat_await_confirm, who)
        self._combat_gate.wait()  # released by the answer, or by `_stop_session` on the way out
        return self._combat_reaction

    def _scene_combat_beat(self, narration: str, who: str) -> None:
        self._clear_thinking()
        label = "You" if who == "pc" else who
        self._scene_status(f"  ⚔ {label}")
        self._scene_dm(inline(narration))

    def _combat_await_confirm(self, combatant: str) -> None:
        """UI-thread: an NPC beat has landed and awaits the player. Free the input and
        arm the confirm gate — Enter confirms, a typed line interjects a reaction."""
        self._combat_awaiting = "confirm"
        self._scene_status(f"— {combatant} acted · Enter to confirm, or type a reaction —",
                           kind="rule")
        self._busy(False)

    def _combat_resolve_confirm(self, text: str) -> None:
        """UI-thread: the player answered the confirm gate. Hand the answer (a reaction,
        or None for a bare-Enter confirm) to the blocked loop worker and let it resume."""
        self._combat_awaiting = None
        self._combat_reaction = text or None
        if text:
            self._scene_player(f"[$success bold]You[/]  {escape(text)}")
        self._busy(True, label="the fight plays out")
        self._scene_thinking("the fight plays out")
        self._combat_gate.set()

    # -- interrupts (ctrl+x, and a call the retries gave up on) ---------------

    def _on_interrupt(self, stage: str, exc: Exception, message: str) -> bool:
        """The loop's `on_interrupt`, on the worker thread: a model call raised instead of
        returning. Reverting the runner session is a backend call, so it happens here before
        the UI is touched — and only for the stages that left a message in the runner's
        context (a cancelled *player-agent* call left nothing to roll back).

        The session survives everything except a hard failure inside a fight. Out of combat
        that is safe — the loop's next act is to ask the player, so nothing is retried until
        a human types — but re-entering a fight goes straight back to the model, so a failure
        there ends the loop rather than grinding against a dead backend."""
        cancelled = isinstance(exc, BackendCancelled)
        if stage == "combat" and not cancelled:
            return False
        if stage in ("turn", "combat"):
            self.game.revert_last_turn()
        self._ui(self._interrupt_ui, stage, exc, message, cancelled)
        return self.is_running  # quitting mid-turn: let the loop end instead of re-asking

    def _interrupt_ui(self, stage: str, exc: Exception, message: str, cancelled: bool) -> None:
        """UI-thread half of `_on_interrupt`: say what happened and hand the message back."""
        self._clear_thinking()
        if not cancelled:
            self._scene_status(f"— the turn failed: {escape(str(exc))} —", kind="error")
            self._busy(False)
        elif stage == "combat":
            # The engine's resume guard rolled the in-flight tracker action back, so the
            # loop re-enters the fight and re-resolves the interrupted combatant cleanly.
            self._scene_status("— combat action cancelled —", kind="rule")
            self._busy(True, label="the fight plays out")
            self._scene_thinking("the fight plays out")
        elif stage == "turn":
            if self._source is not None and not self._source.human:
                # Nobody's draft to hand back — the loop re-asks the player agent.
                self._scene_status("— cancelled — asking again from the same scene —",
                                   kind="rule")
            else:
                self._hand_back(message)
            self._busy(False)
        else:  # "player" — the player agent's own call was cancelled; it'll be asked again
            self._scene_status("— cancelled —", kind="rule")
            self._busy(False)

    def _hand_back(self, text: str) -> None:
        """Give a cancelled message back — into the box if it's empty, or as a scene note if
        a new draft is already in progress."""
        inp = self.query_one("#cmd", Input)
        if inp.value.strip():
            self._scene_status(f'— cancelled — your message was: "{escape(text)}" —', kind="rule")
        else:
            inp.value = text
            inp.cursor_position = len(text)
            self._scene_status("— cancelled — your message is back in the box —", kind="rule")

    # -- phase prompt (yes/no at phase boundaries) ----------------------------

    def on_prompt_bar_answered(self, event: PromptBar.Answered) -> None:
        if event.value:
            self.action_wrap()  # runs whichever phase action is pending
        else:
            what = ("start session 1" if self._pending == "finish_setup"
                    else "start the session" if self._pending == "open"
                    else "wrap the session")
            self._scene_status(f"— not yet — {what} anytime with ctrl+w or the esc menu —")

    # -- cancel (ctrl+x) ----------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel a turn that's mid-flight — e.g. you mistyped and don't want to wait
        out the model call. Aborts the in-flight call so the UI frees up instead of
        locking; the running worker then unwinds with a 'cancelled' note. No-op when
        nothing is running."""
        if self.phase != "play":  # cancel/revert is a play-turn affordance
            return
        if not self._working or self.game is None:
            return
        self.run_worker(self._do_cancel(), exclusive=False)

    async def _do_cancel(self) -> None:
        # The abort POST is quick but still blocks — off the UI thread it goes.
        await asyncio.to_thread(self.game.abort)

    def _cancelled_note(self, msg: str = "— cancelled —") -> None:
        self._clear_thinking()
        self._scene_status(msg, kind="rule")
        self._busy(False)

    def _phase_failed(self, what: str, e: Exception) -> None:
        """A model call failed for good (retries exhausted, server gone): surface it
        in the scene and free the input — a worker exception must never kill the app
        (same contract as _do_wrap/_finish_setup)."""
        self._clear_thinking()
        self._scene_status(f"— {what} failed: {escape(str(e))} —", kind="error")
        self._busy(False)

    # -- wrap: end the session, run the post-session pipeline, open the next -

    def action_wrap(self) -> None:
        """Run the pending phase action: wrap the played session (reconcile + prep
        the next, then open it), or — when setup just finished — plan session 1.
        No-op while busy — except during a watched `--player auto` run, which is *always*
        busy: there the wrap is the only way to stop it, and the source's `stop()` is graceful
        (the turn in flight finishes and is kept)."""
        if self._batch is not None:
            # A bench run wraps itself (`run_once`'s post-wrap tail) — a wrap from here
            # would end play early and record a session the run never finished.
            self.notify("a bench run wraps itself — ctrl+q stops the batch",
                        severity="warning", timeout=3)
            return
        watched = self._loop_live and self._source is not None and not self._source.human
        if self._wrapping or (self._working and not watched):
            return
        if self.game is not None and self.game.in_combat:
            self.notify("finish the fight first — the session can't wrap mid-combat",
                        severity="warning", timeout=3)
            return
        self._prompt.dismiss()  # the prompt's action is being taken (or superseded)
        if self._pending == "finish_setup":
            self._pending = None
            self.run_worker(self._finish_setup(), exclusive=True)
            return
        if self._pending == "open":
            # N+1 is prepped and waiting — open its scene now (the post-wrap start gate).
            self._pending = None
            self.run_worker(self._open(), exclusive=True)
            return
        if self.phase not in ("play", "wrap_pending"):  # nothing to wrap during setup
            return
        self._pending = None
        # The loop still owns the game while it idles on the player — take it down first
        # and let its exit run the wrap (`_session_done`).
        if not self._stop_session(then="wrap"):
            self.run_worker(self._do_wrap(), exclusive=True)
        elif self._working:
            self._scene_status("— wrapping once this turn finishes —", kind="rule")

    async def _do_wrap(self) -> None:
        self._wrapping = True
        self._busy(True, label="wrapping the session")
        self._scene_status("— wrapping the session —", kind="rule")
        # The pane stays closed by default (as in every mode); the pipeline streams into
        # it silently and the scene ticker shows spoiler-free progress — ctrl+g to watch.
        self._write_screen("\n[b]— post-session pipeline —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._announce_stage, "wrap", key)
        # EventTap emits console markup (markup=True) with body text already escaped,
        # so the chunks append as-is — no escape() here or it'd show the tags literally.
        stream = lambda s: self.call_from_thread(self._append_screen, s)
        try:
            new_n = await asyncio.to_thread(self.lc.wrap, ticker, stream)
        except Exception as e:  # noqa: BLE001 — surface any pipeline failure to the player
            self._scene_status(f"— wrap failed: {escape(str(e))} —", kind="error")
            self._wrapping = False
            self._busy(False)
            return
        self._turn = 0
        self._wrapping = False
        # Reconcile + prep are done; N+1 is planned but not opened. Gate the opening
        # (its own model call) behind a yes/no, mirroring the other phase transitions —
        # so the player can inspect the plan (or stop) before the next scene is drafted,
        # instead of auto-burning its first turn.
        self._pending = "open"
        self._busy(False)
        self._scene_status(f"— session {new_n} planned & ready to start —", kind="rule")
        self._prompt.ask(f"Session {new_n} planned — start playing it now?")

    # -- stage ticker (one renderer for every phase's on_stage announcements) -

    # Spoiler-free labels for the stage keys each phase announces (Setup's and the
    # Reconciler's on_stage protocol). One table feeds both the scene ticker and
    # the status bar.
    PHASE_LABELS = {
        "setup": {
            "intake": "gathering your brief · building the world",
            "char": "creating your character",
            "arc-major": "shaping the story",
            "arc-minor": "adding a subplot",
            "state": "setting the opening scene",
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

    def _announce_stage(self, phase: str, key: str) -> None:
        label = self.PHASE_LABELS.get(phase, {}).get(key, key)
        self._scene_status(f"  ▸ {label}…")
        self._status.set_phase(label)

    # -- turn detail (behind the screen) --------------------------------------

    def _render_turn_detail(self, tr) -> None:
        self._turn += 1
        tools = ", ".join(sorted(tr.tools)) or "none"
        self._write_screen(f"\n[b]turn {self._turn}[/b]  tools: {tools}")

    # -- menu (esc) -----------------------------------------------------------

    def action_menu(self) -> None:
        """The mouse-and-arrow surface over the same actions the keybinds drive."""
        if isinstance(self.screen, ModalScreen):
            return  # a modal is already up
        in_setup = self.phase == "setup"
        idle = not self._working and not self._wrapping
        if self._pending == "finish_setup":
            wrap_label, wrap_ok = "Finish setup → session 1  (^w)", idle
        elif self._pending == "open":
            wrap_label, wrap_ok = "Start the planned session  (^w)", idle
        else:
            wrap_label, wrap_ok = "Wrap session  (^w)", idle and not in_setup
        if self._batch is not None:  # a run wraps itself; nothing here drives it
            wrap_label, wrap_ok = "Wrap session  (^w)", False
        items = [
            ("status", "Campaign status", self.lc is None),
            ("wrap", wrap_label, not wrap_ok),
            ("cancel", "Cancel turn  (^x)", in_setup or not self._working),
            ("screen", "Toggle behind-screen  (^g)", False),
            ("mode", f"Switch to {'META' if self.mode == 'action' else 'ACTION'} mode  (^t)",
             in_setup or self._batch is not None),
            ("roll", "Roll dice…", False),
            ("quit", "Quit  (^q)", False),
        ]
        self.push_screen(MenuScreen(items), self._menu_selected)

    def _menu_selected(self, choice: str | None) -> None:
        if choice == "status":
            self.run_worker(self._show_status(), exclusive=False)
        elif choice == "wrap":
            self.action_wrap()
        elif choice == "cancel":
            self.action_cancel()
        elif choice == "screen":
            self.action_toggle_screen()
        elif choice == "mode":
            self.action_toggle_mode()
        elif choice == "roll":
            self.push_screen(RollScreen(), self._roll_submitted)
        elif choice == "quit":
            self.exit()

    async def _show_status(self) -> None:
        # Disk + lint + git subprocesses — off the UI thread, then render.
        st = await asyncio.to_thread(self.lc.status)
        self.push_screen(StatusScreen(st))

    def _roll_submitted(self, expr: str | None) -> None:
        if not expr:
            return
        result = roll_expr(expr)
        self._scene_status(result or f"could not parse “{escape(expr)}” — try 2d6+3", kind="rule")

    # -- actions ------------------------------------------------------------

    def action_toggle_screen(self) -> None:
        log = self.query_one("#screen", RichLog)
        log.toggle_class("hidden")
        # When revealing, jump to the most recent content (the stream may have
        # been accumulating while the pane was closed).
        if not log.has_class("hidden"):
            log.scroll_end(animate=False)

    def action_toggle_mode(self) -> None:
        if self._batch is not None:
            return  # watching, not playing — there is no mode to be in
        if self.phase == "setup":
            return  # setup has no modes — the bar is always a DM answer
        self.mode = "meta" if self.mode == "action" else "action"
        self._sync_input()
        self._refresh_subtitle()

    async def on_unmount(self) -> None:
        # Release the loop's worker thread before anything else: it is parked on the player
        # source, and a thread left parked there keeps the interpreter from exiting.
        self._stop_session()
        if self.cleanup:
            self.cleanup()


def roll_expr(expr: str) -> str | None:
    """Minimal dice roller: NdM with +/- integer or dice modifiers (e.g.
    `d20+7`, `2d6-1`, `4d6+1d4`). Not the full grammar — keeps the human's
    rolls honest without a parser the prototype doesn't need."""
    e = expr.strip().lower()
    terms = re.findall(r"([+-]?)\s*(\d*d\d+|\d+)", e)
    if not terms or "".join(s + t for s, t in terms).replace(" ", "") != e.replace(" ", ""):
        return None
    total, detail = 0, []
    for sign, term in terms:
        neg = sign == "-"
        if "d" in term:
            n_s, faces_s = term.split("d")
            n, faces = int(n_s or 1), int(faces_s)
            if not (1 <= n <= 100 and faces >= 1):
                return None
            rolls = [random.randint(1, faces) for _ in range(n)]
            value, detail = sum(rolls), detail + [f"{sign or '+'}{term}({','.join(map(str, rolls))})"]
        else:
            value = int(term)
            detail.append(f"{sign or '+'}{term}")
        total += -value if neg else value
    return f"🎲 {expr} = {total}   ({' '.join(detail)})"
