"""
PlayApp — the rich-TUI front-end over the orchestrator `Game`.

Layout: a scene pane (the play — DM narration + your lines), a behind-the-screen
pane (live model stream + per-turn gate verdicts), and an input that switches
between ACTION mode (gated turn) and META mode (out-of-game question, ungated).

The scene pane is a selectable `Static` (so you can copy DM narration) with a
capped buffer so re-renders stay O(1) as the session grows — the full transcript
is always on disk at `campaign/sessions/session-{N}-transcript.md`. The
behind-the-screen pane is a `RichLog` — append-efficient (no O(n²) re-render on
each write), but not text-selectable. The full gate log is on disk at
`/tmp/orchestrator-checks.log`.

Model calls block, so they run off the UI thread (`asyncio.to_thread`) with the
input disabled while a turn resolves. Two signals keep the app from going silent
for minutes:

  - **Heartbeat:** a 1s tick that shows elapsed time in the subtitle while busy
    (`⏳ the table is thinking… 0:42`). If the timer is ticking, the app is
    responsive; if it freezes, the TUI itself is lagged — disambiguating "lag"
    from "working."
  - **Live stream:** an `EventTap` routes live model output (tokens + tool calls)
    into the behind-the-screen pane during every phase — play turns, meta,
    setup, and wrap. The pane stays closed by default; open it with ctrl+g to
    watch. The stream accumulates in the `RichLog`, so opening it mid-turn
    reveals everything that's happened so far.

The app talks only to a Game-like object (`start`/`turn`/`meta` → `TurnResult`),
so the same UI runs against `MockGame` or the real backend.
"""

from __future__ import annotations

import asyncio
import random
import re
import time

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, RichLog, Static

from orchestrator.backend import BackendCancelled
from orchestrator.textmarkup import inline


class PlayApp(App):
    CSS = """
    #main   { height: 1fr; }
    #scene  { width: 2fr; border: round $primary;   padding: 0 1; }
    #screen { width: 1fr; border: round $secondary; }
    #screen.hidden { display: none; }
    #cmd { height: 3; border: tall $accent; }
    #cmd:disabled { border: tall $surface; }
    """

    BINDINGS = [
        ("ctrl+g", "toggle_screen", "Behind-screen"),
        ("ctrl+t", "toggle_mode", "Action/Meta"),
        ("ctrl+x", "cancel", "Cancel turn"),
        ("ctrl+w", "wrap", "Wrap session"),
        ("ctrl+q", "quit", "Quit"),
    ]

    # Cap the scene pane's buffer so Static re-renders stay O(1) as the session
    # grows. The full transcript is always on disk — this is just the visible
    # scrollback. Once the cap is hit, the oldest lines are dropped and a marker
    # is prepended so the truncation is visible.
    _SCENE_MAX = 50000
    _TRUNCATED_MARKER = (
        "[$text-muted]… older lines truncated — "
        "full transcript in campaign/sessions/ …[/]\n"
    )

    def __init__(self, lifecycle, cleanup=None, theme: str = "dracula"):
        super().__init__()
        self.lc = lifecycle
        self.cleanup = cleanup
        self._theme = theme
        self.mode = "action"
        self._turn = 0
        self._wrapping = False
        self._scene = ""
        self._setup_tap = None       # EventTap streaming setup authoring behind the screen
        self._setup_hidden = True    # screen pane's visibility before setup borrowed it
        self._setup_stages_seen = set()  # spoiler-free setup stages already shown (each shows once)
        # Heartbeat: a 1s tick that shows elapsed time in the subtitle while busy,
        # so a responsive-but-waiting app is distinguishable from a frozen one.
        self._busy_start: float | None = None
        self._busy_label: str | None = None
        self._heartbeat = None       # the Timer, while busy

    @property
    def game(self):
        """The session currently in play; the lifecycle swaps it on wrap."""
        return self.lc.game

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with VerticalScroll(id="scene"):
                yield Static(id="scene-body", markup=True)
            # RichLog: append-efficient (no O(n²) re-render), handles its own
            # scrolling, parses console markup (so EventTap's markup dialect
            # renders coloured). Not text-selectable — the full gate log is on
            # disk at /tmp/orchestrator-checks.log.
            # min_width=0 overrides RichLog's default of 78 columns, which
            # otherwise forces the pane wider than its 1fr layout slot and
            # produces a horizontal scrollbar (wrapping at 78, not at the
            # pane's actual width).
            yield RichLog(id="screen", markup=True, wrap=True, auto_scroll=False,
                          min_width=0, classes="hidden")
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = self._theme if self._theme in self.available_themes else "dracula"
        self._write("screen", "[b]behind the screen[/b] — live model stream · gate verdicts")
        self._write("scene", "[$text-muted]ctrl+t action/meta · ctrl+g behind-screen · ctrl+x cancel · ctrl+w wrap · /roll 2d6+3 · /meta <q> · /quit[/]")
        self._sync_input()
        self.sub_title = "ACTION mode"
        self.run_worker(self._open(), exclusive=True)

    # -- panes --------------------------------------------------------------

    def _write(self, pane: str, markup: str) -> None:
        self._append(pane, markup + "\n")

    def _append(self, pane: str, text: str) -> None:
        """Append raw text (possibly partial, possibly multi-line) to a pane."""
        if pane == "scene":
            self._append_scene(text)
        else:
            self._append_screen(text)

    def _append_scene(self, text: str) -> None:
        """Scene pane: a capped Static string (selectable, O(1) re-renders).

        Concatenates into the buffer and re-renders the whole string on each
        write — fine because the buffer is capped. Auto-follows only when the
        view is already pinned to the bottom, so a reader scrolled up to read
        back isn't yanked down on the next write."""
        self._scene += text
        if len(self._scene) > self._SCENE_MAX:
            keep = self._SCENE_MAX - len(self._TRUNCATED_MARKER)
            self._scene = self._TRUNCATED_MARKER + self._scene[-keep:]
        self.query_one("#scene-body", Static).update(self._scene)
        container = self.query_one("#scene", VerticalScroll)
        if container.scroll_offset.y >= container.max_scroll_y - 2:
            container.scroll_end(animate=False)

    def _append_screen(self, text: str) -> None:
        """Screen pane: a RichLog. Each chunk is written as a single renderable
        so console markup — including tags that span newlines, like the headings
        and tool-call lines EventTap emits — parses correctly. RichLog handles
        the visual line splitting internally; each write() appends to the log
        without re-rendering what's already there (no O(n²) cost).

        Auto-follows only when pinned to the bottom, so a reader scrolled up
        isn't yanked down on the next streamed chunk."""
        if not text:
            return
        log = self.query_one("#screen", RichLog)
        follow = log.scroll_offset.y >= log.max_scroll_y - 2
        log.write(text, scroll_end=follow)

    # -- input mode & heartbeat ---------------------------------------------

    def _sync_input(self) -> None:
        inp = self.query_one("#cmd", Input)
        if self.lc.phase == "setup":
            inp.border_title = "SETUP — talk to the DM"
            inp.placeholder = "Answer the DM…"
        elif self.mode == "action":
            inp.border_title = "ACTION — gated"
            inp.placeholder = "What does your character do?"
        else:
            inp.border_title = "META — out-of-game, ungated"
            inp.placeholder = "Ask the DM a logistical question…"

    def _default_busy_label(self) -> str:
        if self.lc.phase == "setup":
            return "the DM is building"
        if self._wrapping:
            return "wrapping the session"
        return "the table is thinking"

    def _busy(self, busy: bool, label: str | None = None) -> None:
        inp = self.query_one("#cmd", Input)
        inp.disabled = busy
        if busy:
            inp.border_title = "…thinking…"
            # Don't reset the elapsed clock on re-entry (e.g. _do_wrap called
            # while a turn's busy is already active) — the wait is continuous.
            if self._busy_start is None:
                self._busy_start = time.monotonic()
            self._busy_label = label or self._default_busy_label()
            if self._heartbeat is None:
                self._heartbeat = self.set_interval(1, self._tick_heartbeat,
                                                    name="heartbeat")
            self._tick_heartbeat()
        else:
            if self._heartbeat is not None:
                self._heartbeat.stop()
                self._heartbeat = None
            self._busy_start = None
            self._busy_label = None
            self._sync_input()
            self.sub_title = "SETUP" if self.lc.phase == "setup" else f"{self.mode.upper()} mode"
            inp.focus()

    def _set_busy_label(self, label: str) -> None:
        """Update the heartbeat label mid-busy (e.g. setup → planning session 1)."""
        self._busy_label = label
        self._tick_heartbeat()

    def _tick_heartbeat(self) -> None:
        if self._busy_start is None or self._busy_label is None:
            return
        elapsed = int(time.monotonic() - self._busy_start)
        m, s = divmod(elapsed, 60)
        self.sub_title = f"⏳ {self._busy_label}… {m}:{s:02d}"

    # -- play stream (live model output → behind-the-screen pane) -----------

    def _start_stream(self):
        """Start an EventTap routing live model output (streaming tokens + tool
        calls) into the behind-the-screen pane. The pane stays closed by
        default — toggle it with ctrl+g to watch. The stream accumulates in the
        RichLog, so opening it mid-turn reveals everything that's happened so
        far. Returns the tap (or None); the caller stops it when the blocking
        call returns."""
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
        return self.lc.play_stream(stream)

    # -- game interaction (off the UI thread) -------------------------------

    async def _open(self) -> None:
        self._busy(True)
        if self.lc.phase == "setup":
            await self._open_setup()   # _open_setup starts its own stream
            return
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
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread, same
            # pattern as _finish_setup.
            if tap:
                await asyncio.to_thread(tap.stop)
        if resumed:
            self._write("scene", "[$text-muted]— resuming the session in progress —[/]")
        self._write("scene", f"\n[$accent]DM[/]  {inline(scene)}")
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
            self._write("scene", f"[$text-muted]  ▸ {stage}…[/]")

    async def _open_setup(self) -> None:
        """Open a brand-new campaign: a guided conversation in the scene pane, with the
        dm's authoring streamed behind the screen for the whole setup."""
        screen = self.query_one("#screen", RichLog)
        self._setup_hidden = screen.has_class("hidden")
        screen.remove_class("hidden")
        self._write("screen", "\n[b]— building the campaign —[/b]\n")
        self._setup_stages_seen.clear()
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
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
        self._write("scene", f"\n[$accent]DM[/]  {inline(st.reply)}")
        if st.done:
            await self._finish_setup()
        else:
            self._busy(False)

    async def _do_setup(self, text: str) -> None:
        self._busy(True)
        try:
            st = await asyncio.to_thread(self.lc.setup.turn, text)
        except BackendCancelled:
            self._cancelled_note()
            return
        self._write("scene", f"\n[$accent]DM[/]  {inline(st.reply)}")
        if st.done:
            await self._finish_setup()
        else:
            self._busy(False)

    async def _finish_setup(self) -> None:
        """Setup reported done: plan session 1 (behind the screen), then open play(1)."""
        if self._setup_tap:
            # stop() flushes the tap's buffered line through the write callback
            # (call_from_thread) — so it must run off the app thread, not here.
            await asyncio.to_thread(self._setup_tap.stop)
            self._setup_tap = None
        self._set_busy_label("planning session 1")
        self._write("scene", "\n[$warning]— campaign built · planning session 1 —[/]")
        self._write("screen", "\n[b]— planning session 1 —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._announce_stage, "setup", key)
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
        try:
            n = await asyncio.to_thread(self.lc.finish_setup, ticker, stream)
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._write("scene", f"\n[$error]— setup failed: {escape(str(e))} —[/]")
            self._busy(False)
            return
        if self._setup_hidden:
            self.query_one("#screen", RichLog).add_class("hidden")
        self._write("scene", f"\n[$success]— campaign ready · opening session {n} —[/]")
        self._turn = 0
        await self._open()  # phase is now "play" → opens session 1

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        if text.lower() in ("/quit", "/exit", "/q"):
            self.exit()
            return
        # During setup the bar is a plain answer to the DM — no play commands apply.
        if self.lc.phase == "setup":
            if self.query_one("#cmd", Input).disabled:
                return
            self._write("scene", f"\n[$success]You[/]  {inline(text)}")
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
            self._write("scene", f"\n[$warning]{result or 'could not parse — try /roll 2d6+3'}[/]")
            return
        # /meta — an out-of-game question without switching modes.
        if text.lower().startswith("/meta"):
            q = text[5:].strip()
            if q:
                self._write("scene", f"\n[$text-muted]You (out-of-game)  {escape(q)}[/]")
                self.run_worker(self._do_meta(q), exclusive=True)
            return

        if self.mode == "action":
            self._write("scene", f"\n[$success]You[/]  {escape(text)}")
            self.run_worker(self._do_turn(text), exclusive=True)
        else:
            self._write("scene", f"\n[$text-muted]You (out-of-game)  {escape(text)}[/]")
            self.run_worker(self._do_meta(text), exclusive=True)

    async def _do_turn(self, text: str) -> None:
        self._busy(True)
        tap = self._start_stream()
        try:
            tr = await asyncio.to_thread(self.game.turn, text)
        except BackendCancelled:
            await self._cancel_cleanup(text)
            return
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread.
            if tap:
                await asyncio.to_thread(tap.stop)
        self._render_dm(tr)
        self._render_turn_status(tr)
        self._render_gate(tr)
        if tr.session_complete:
            # The runner signalled the session's end — roll straight into the wrap
            # (capture handoff notes, reconcile, open N+1), the same path as ctrl+w.
            self._write("scene", "\n[$warning]— the session has reached its end —[/]")
            await self._do_wrap()
            return
        self._busy(False)

    async def _do_meta(self, question: str) -> None:
        self._busy(True)
        tap = self._start_stream()
        try:
            answer = await asyncio.to_thread(self.game.meta, question)
        except BackendCancelled:
            await self._cancel_cleanup(question)
            return
        finally:
            # stop() flushes buffered stream content through the write callback
            # (which uses call_from_thread) — must run off the app thread.
            if tap:
                await asyncio.to_thread(tap.stop)
        self._write("scene", f"[$text-muted]DM (out-of-game)  {inline(answer)}[/]")
        self._busy(False)

    # -- cancel (ctrl+x) ----------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel a turn that's mid-flight — e.g. you mistyped and don't want to wait
        out the model call. Aborts the in-flight call so the UI frees up instead of
        locking; the running worker then unwinds with a 'cancelled' note. No-op when
        nothing is running (the input is live)."""
        if self.lc.phase != "play":  # cancel/revert is a play-turn affordance
            return
        if not self.query_one("#cmd", Input).disabled:
            return
        self.run_worker(self._do_cancel(), exclusive=False)

    async def _do_cancel(self) -> None:
        # The abort POST is quick but still blocks — off the UI thread it goes.
        await asyncio.to_thread(self.game.abort)

    async def _cancel_cleanup(self, text: str) -> None:
        """After a cancelled turn/meta: drop the abandoned exchange from the runner's
        context, free the input, and drop the cancelled message back in the box so
        you can fix the typo and resend instead of retyping it."""
        await asyncio.to_thread(self.game.revert_last_turn)
        self._busy(False)
        inp = self.query_one("#cmd", Input)
        inp.value = text
        inp.cursor_position = len(text)
        self._write("scene", "\n[$warning]— cancelled — your message is back in the box —[/]")

    def _cancelled_note(self, msg: str = "— cancelled —") -> None:
        self._write("scene", f"\n[$warning]{msg}[/]")
        self._busy(False)

    # -- wrap: end the session, run the post-session pipeline, open the next -

    def action_wrap(self) -> None:
        """Wrap the played session: run the post-session pipeline (reconcile + prep the
        next), then open session N+1 — without leaving the app. No-op while busy."""
        if self.lc.phase != "play":  # nothing to wrap during setup
            return
        if self._wrapping or self.query_one("#cmd", Input).disabled:
            return
        self.run_worker(self._do_wrap(), exclusive=True)

    async def _do_wrap(self) -> None:
        self._wrapping = True
        self._busy(True, label="wrapping the session")
        self._write("scene", "\n[$warning]— wrapping the session —[/]")
        # Reveal the behind-the-screen pane so the live pipeline stream is visible,
        # remembering whether it was hidden so we can restore that afterward (it stays
        # closed by default — the wrap just borrows it).
        screen = self.query_one("#screen", RichLog)
        was_hidden = screen.has_class("hidden")
        screen.remove_class("hidden")
        self._write("screen", "\n[b]— post-session pipeline —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._announce_stage, "wrap", key)
        # EventTap emits console markup (markup=True) with body text already escaped,
        # so the chunks append as-is — no escape() here or it'd show the tags literally.
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
        try:
            new_n = await asyncio.to_thread(self.lc.wrap, ticker, stream)
        except Exception as e:  # noqa: BLE001 — surface any pipeline failure to the player
            self._write("scene", f"\n[$error]— wrap failed: {escape(str(e))} —[/]")
            self._wrapping = False
            self._busy(False)
            return
        self._write("scene", f"\n[$success]— session {new_n} ready · opening the scene —[/]")
        if was_hidden:
            screen.add_class("hidden")  # restore the default closed state
        self._turn = 0
        self._wrapping = False
        await self._open()  # opens the next session's scene and re-enables input

    # -- stage ticker (one renderer for every phase's on_stage announcements) -

    # Spoiler-free labels for the stage keys each phase announces (Setup's and the
    # Reconciler's on_stage protocol). One table, one renderer — a richer progress
    # UI later plugs in here without touching the orchestrator.
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
        self._write("scene", f"[$text-muted]  ▸ {label}…[/]")

    # -- rendering ----------------------------------------------------------

    def _render_dm(self, tr) -> None:
        self._write("scene", f"\n[$accent]DM[/]  {inline(tr.final)}")

    def _render_turn_status(self, tr) -> None:
        """One muted line per gated turn in the scene pane, so the player sees the
        loop working without opening the behind-the-screen pane."""
        g = tr.gate
        if tr.corrected:
            fixed = [n for n, v in (("canon", g.narrative), ("conduct", g.conduct)) if not v.passed]
            self._write("scene",
                        f"[$text-muted]  ✎ corrected ({' + '.join(fixed) or 'gate'}) — ctrl+g for details[/]")
        else:
            self._write("scene", "[$text-muted]  ✓ checked[/]")

    def _render_gate(self, tr) -> None:
        self._turn += 1
        g = tr.gate
        # Standard Rich color names (not Textual $-tokens): the screen pane is a
        # RichLog, which parses markup with Rich's parser — $-tokens like
        # [$success] are Textual-specific and Rich sees the [/] closer as orphaned.
        nv = "[green]PASS[/]" if g.narrative.passed else "[red]VIOLATIONS[/]"
        cv = "[green]PASS[/]" if g.conduct.passed else "[red]VIOLATIONS[/]"
        status = "[yellow]CORRECTED[/]" if tr.corrected else "[green]clean[/]"
        self._write("screen", f"\n[b]turn {self._turn}[/b]  canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon")
        if not g.narrative.passed:
            self._write("screen", f"[red]canon[/]\n{inline(g.narrative.report.strip())}")
        if not g.conduct.passed:
            self._write("screen", f"[red]conduct[/]\n{inline(g.conduct.report.strip())}")

    # -- actions ------------------------------------------------------------

    def action_toggle_screen(self) -> None:
        log = self.query_one("#screen", RichLog)
        log.toggle_class("hidden")
        # When revealing, jump to the most recent content (the stream may have
        # been accumulating while the pane was closed).
        if not log.has_class("hidden"):
            log.scroll_end(animate=False)

    def action_toggle_mode(self) -> None:
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
