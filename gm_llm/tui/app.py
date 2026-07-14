"""
PlayApp — the rich-TUI front-end over the orchestrator `Game`.

Layout: a scene pane (the play — DM narration + your lines, one selectable
block per beat), a behind-the-screen pane (live model stream + per-turn gate
verdicts), a status bar (what the table is doing right now), a phase prompt
bar (yes/no at phase boundaries), and an input that switches between ACTION
mode (gated turn) and META mode (out-of-game question, ungated).

The scene pane mounts one widget per beat (see tui/widgets.py) into a
`VerticalScroll`, capped at `_SCENE_MAX_BLOCKS` — the full transcript is
always on disk at `campaign/sessions/session-{N}-transcript.md`. The
behind-the-screen pane is a `RichLog` — append-efficient, but not
text-selectable; the full gate log is on disk under the project's log dir
(`.opencode/logs/orchestrator-checks.log`).

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
"""

from __future__ import annotations

import asyncio
import random
import re

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, RichLog

from gm_llm.orchestrator.backend import BackendCancelled
from gm_llm.orchestrator.textmarkup import inline

from .screens import MenuScreen, RollScreen, StatusScreen
from .widgets import DMBlock, PendingBlock, PlayerLine, PromptBar, SceneLine, StatusBar


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
        "check": "checking canon & conduct",
        "correct": "revising the narration",
        "done": "finishing up",
    }

    def __init__(self, lifecycle, cleanup=None, theme: str = "dracula"):
        super().__init__()
        self.lc = lifecycle
        self.cleanup = cleanup
        self._theme = theme
        self.mode = "action"
        self._turn = 0
        self._working = False        # a worker owns the table; submits are held
        self._wrapping = False
        self._pending = None         # phase action awaiting a yes: "wrap" | "finish_setup"
        self._thinking = None        # the PendingBlock in the scene, while a call is in flight
        self._setup_tap = None       # EventTap streaming setup authoring behind the screen
        self._setup_stages_seen = set()  # spoiler-free setup stages already shown (each shows once)

    @property
    def game(self):
        """The session currently in play; the lifecycle swaps it on wrap."""
        return self.lc.game

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield VerticalScroll(id="scene")
            # RichLog: append-efficient (no O(n²) re-render), handles its own
            # scrolling, parses console markup (so EventTap's markup dialect
            # renders coloured). Not text-selectable — the full gate log is on
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
        self._write_screen("[b]behind the screen[/b] — live model stream · gate verdicts")
        self._scene_status("esc menu · ctrl+t action/meta · ctrl+g behind-screen · "
                           "ctrl+x cancel · ctrl+w wrap · /roll 2d6+3 · /meta <q> · /quit")
        # Backend retries surface in the status bar ("call failed — retry …"),
        # so a rate-limited wait doesn't look like a hang.
        self.lc.backend.on_retry = lambda agent, attempt, wait, reason: \
            self.call_from_thread(self._status.note,
                                  f"⚠ {agent} call failed ({escape(str(reason))}) — "
                                  f"retry {attempt} in {int(wait)}s")
        self._sync_input()
        self.sub_title = "ACTION mode"
        if self.lc.phase == "wrap_pending":
            # A prior run ended session N (task_complete fired) and the player
            # never confirmed the wrap — show the same choice again, no model
            # call, no resume: reconcile-and-prep or quit, nothing else.
            self._show_wrap_pending()
            return
        self.run_worker(self._open(), exclusive=True)

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
        if self._working:
            inp.border_title = "…thinking — draft freely, send once the table frees up…"
        elif self.lc.phase == "setup":
            inp.border_title = "SETUP — talk to the DM"
        elif self._pending == "wrap":
            inp.border_title = "SESSION COMPLETE — reconcile or quit, nothing else"
        elif self.mode == "action":
            inp.border_title = "ACTION — gated"
        else:
            inp.border_title = "META — out-of-game, ungated"
        inp.placeholder = ("Answer the DM…" if self.lc.phase == "setup"
                           else "Y to wrap, N not yet, or /quit" if self._pending == "wrap"
                           else "What does your character do?" if self.mode == "action"
                           else "Ask the DM a logistical question…")

    def _default_busy_label(self) -> str:
        if self.lc.phase == "setup":
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
            self.sub_title = "SETUP" if self.lc.phase == "setup" else f"{self.mode.upper()} mode"
            self.query_one("#cmd", Input).focus()

    def _turn_step(self, key: str) -> None:
        self._status.set_phase(self.TURN_STEPS.get(key, key))

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
        if self.lc.phase == "setup":
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
        self._busy(False)

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
        if self.lc.phase == "setup":
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
            self._scene_player(f"[$success bold]You[/]  {escape(text)}")
            self.run_worker(self._do_turn(text), exclusive=True)
        else:
            self._scene_player(f"You (out-of-game)  {escape(text)}", meta=True)
            self.run_worker(self._do_meta(text), exclusive=True)

    async def _do_turn(self, text: str) -> None:
        self._busy(True)
        self._scene_thinking()
        tap = self._start_stream()
        try:
            tr = await asyncio.to_thread(self.game.turn, text)
        except BackendCancelled:
            await self._cancel_cleanup(text)
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("the turn", e)
            return
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread.
            if tap:
                await asyncio.to_thread(tap.stop)
        self._clear_thinking()
        block = self._scene_dm(inline(tr.final))
        g = tr.gate
        fixed = [n for n, v in (("canon", g.narrative), ("conduct", g.conduct)) if not v.passed]
        block.set_gate(tr.corrected, fixed)
        self._render_gate(tr)
        if tr.session_complete:
            # The runner signalled the session's end — offer the wrap (reconcile +
            # prep N+1) instead of auto-running minutes of pipeline.
            self._scene_status("— the session has reached its end —", kind="rule")
            self._pending = "wrap"
            self._busy(False)
            self._prompt.ask(f"Session {self.lc.session} complete — "
                             f"reconcile & prep session {self.lc.session + 1}?")
            return
        self._busy(False)

    async def _do_meta(self, question: str) -> None:
        self._busy(True)
        self._scene_thinking("the DM is answering")
        tap = self._start_stream()
        try:
            answer = await asyncio.to_thread(self.game.meta, question)
        except BackendCancelled:
            await self._cancel_cleanup(question)
            return
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._phase_failed("the question", e)
            return
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread.
            if tap:
                await asyncio.to_thread(tap.stop)
        self._clear_thinking()
        self._scene_dm(inline(answer), meta=True)
        self._busy(False)

    # -- phase prompt (yes/no at phase boundaries) ----------------------------

    def on_prompt_bar_answered(self, event: PromptBar.Answered) -> None:
        if event.value:
            self.action_wrap()  # runs whichever phase action is pending
        else:
            what = ("start session 1" if self._pending == "finish_setup"
                    else "wrap the session")
            self._scene_status(f"— not yet — {what} anytime with ctrl+w or the esc menu —")

    # -- cancel (ctrl+x) ----------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel a turn that's mid-flight — e.g. you mistyped and don't want to wait
        out the model call. Aborts the in-flight call so the UI frees up instead of
        locking; the running worker then unwinds with a 'cancelled' note. No-op when
        nothing is running."""
        if self.lc.phase != "play":  # cancel/revert is a play-turn affordance
            return
        if not self._working:
            return
        self.run_worker(self._do_cancel(), exclusive=False)

    async def _do_cancel(self) -> None:
        # The abort POST is quick but still blocks — off the UI thread it goes.
        await asyncio.to_thread(self.game.abort)

    async def _cancel_cleanup(self, text: str) -> None:
        """After a cancelled turn/meta: drop the abandoned exchange from the runner's
        context, free the input, and give the cancelled message back — into the box
        if it's empty, or as a scene note if a new draft is already in progress."""
        await asyncio.to_thread(self.game.revert_last_turn)
        self._clear_thinking()
        self._busy(False)
        inp = self.query_one("#cmd", Input)
        if inp.value.strip():
            self._scene_status(f'— cancelled — your message was: "{escape(text)}" —', kind="rule")
        else:
            inp.value = text
            inp.cursor_position = len(text)
            self._scene_status("— cancelled — your message is back in the box —", kind="rule")

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
        No-op while busy."""
        if self._working or self._wrapping:
            return
        self._prompt.dismiss()  # the prompt's action is being taken (or superseded)
        if self._pending == "finish_setup":
            self._pending = None
            self.run_worker(self._finish_setup(), exclusive=True)
            return
        if self.lc.phase not in ("play", "wrap_pending"):  # nothing to wrap during setup
            return
        self._pending = None
        self.run_worker(self._do_wrap(), exclusive=True)

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
        self._scene_status(f"— session {new_n} ready · opening the scene —", kind="success")
        self._turn = 0
        self._wrapping = False
        await self._open()  # opens the next session's scene and re-enables input

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
            "assess": "taking stock of what happened",
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

    # -- gate detail (behind the screen) --------------------------------------

    def _render_gate(self, tr) -> None:
        self._turn += 1
        g = tr.gate
        # Standard Rich color names (not Textual $-tokens): the screen pane is a
        # RichLog, which parses markup with Rich's parser — $-tokens like
        # [$success] are Textual-specific and Rich sees the [/] closer as orphaned.
        nv = "[green]passed[/]" if g.narrative.passed else "[red]violations[/]"
        cv = "[green]passed[/]" if g.conduct.passed else "[red]violations[/]"
        status = "[yellow]CORRECTED[/]" if tr.corrected else "[green]clean[/]"
        self._write_screen(f"\n[b]turn {self._turn}[/b]  canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon")
        if not g.narrative.passed:
            self._write_screen(f"[red]canon[/]\n{inline(g.narrative.report.strip())}")
        if not g.conduct.passed:
            self._write_screen(f"[red]conduct[/]\n{inline(g.conduct.report.strip())}")

    # -- menu (esc) -----------------------------------------------------------

    def action_menu(self) -> None:
        """The mouse-and-arrow surface over the same actions the keybinds drive."""
        if isinstance(self.screen, ModalScreen):
            return  # a modal is already up
        in_setup = self.lc.phase == "setup"
        idle = not self._working and not self._wrapping
        if self._pending == "finish_setup":
            wrap_label, wrap_ok = "Finish setup → session 1  (^w)", idle
        else:
            wrap_label, wrap_ok = "Wrap session  (^w)", idle and not in_setup
        items = [
            ("status", "Campaign status", False),
            ("wrap", wrap_label, not wrap_ok),
            ("cancel", "Cancel turn  (^x)", in_setup or not self._working),
            ("screen", "Toggle behind-screen  (^g)", False),
            ("mode", f"Switch to {'META' if self.mode == 'action' else 'ACTION'} mode  (^t)",
             in_setup),
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
        if self.lc.phase == "setup":
            return  # setup has no modes — the bar is always a DM answer
        self.mode = "meta" if self.mode == "action" else "action"
        self._sync_input()
        self.sub_title = f"{self.mode.upper()} mode"

    async def on_unmount(self) -> None:
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
