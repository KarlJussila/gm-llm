"""
PlayApp — the rich-TUI front-end over the orchestrator `Game`.

Layout: a scene pane (the play — DM narration + your lines), a toggleable
behind-the-screen pane (per-turn gate verdicts), and an input that switches
between ACTION mode (gated turn) and META mode (out-of-game question, ungated).

The panes are scrollable `Static`s rather than `RichLog`s on purpose: RichLog
renders opaque strips and can't be text-selected, but Static renders Content, so
you can select and copy (ctrl+c) the scene.

Model calls block, so they run off the UI thread (`asyncio.to_thread`) with the
input disabled while a turn resolves. The app talks only to a Game-like object
(`start`/`turn`/`meta` → TurnResult), so the same UI runs against MockGame or the
real backend.
"""

from __future__ import annotations

import asyncio
import random
import re

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from orchestrator.backend import BackendCancelled
from orchestrator.textmarkup import inline


class PlayApp(App):
    CSS = """
    #main   { height: 1fr; }
    #scene  { width: 2fr; border: round $primary;   padding: 0 1; }
    #screen { width: 1fr; border: round $secondary; padding: 0 1; }
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

    def __init__(self, lifecycle, cleanup=None, theme: str = "dracula"):
        super().__init__()
        self.lc = lifecycle
        self.cleanup = cleanup
        self._theme = theme
        self.mode = "action"
        self._turn = 0
        self._wrapping = False
        self._scene = ""
        self._screen = ""
        self._setup_tap = None       # EventTap streaming setup authoring behind the screen
        self._setup_hidden = True    # screen pane's visibility before setup borrowed it
        self._setup_stage = None     # last spoiler-free setup stage shown in the scene

    @property
    def game(self):
        """The session currently in play; the lifecycle swaps it on wrap."""
        return self.lc.game

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with VerticalScroll(id="scene"):
                yield Static(id="scene-body", markup=True)
            with VerticalScroll(id="screen", classes="hidden"):
                yield Static(id="screen-body", markup=True)
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = self._theme if self._theme in self.available_themes else "dracula"
        self._write("screen", "[b]behind the screen[/b] — gate verdicts")
        self._write("scene", "[$text-muted]ctrl+t action/meta · ctrl+g behind-screen · ctrl+x cancel · ctrl+w wrap · /roll 2d6+3 · /meta <q> · /quit[/]")
        self._sync_input()
        self.sub_title = "ACTION mode"
        self.run_worker(self._open(), exclusive=True)

    # -- panes (selectable Statics) ----------------------------------------

    def _write(self, pane: str, markup: str) -> None:
        self._append(pane, markup + "\n")

    def _append(self, pane: str, text: str) -> None:
        """Append raw text to a pane's buffer — used for line writes and for the
        streamed reconcile log, which arrives in arbitrary (non-line) chunks."""
        container = self.query_one(f"#{pane}", VerticalScroll)
        # Auto-follow only when the view is already pinned to the bottom. If the
        # reader scrolled up to read back, leave them there instead of yanking them
        # down on the next write (the streamed wrap log writes constantly).
        follow = container.scroll_offset.y >= container.max_scroll_y - 2
        if pane == "scene":
            self._scene += text
            buf = self._scene
        else:
            self._screen += text
            buf = self._screen
        self.query_one(f"#{pane}-body", Static).update(buf)
        if follow:
            container.scroll_end(animate=False)

    # -- input mode ---------------------------------------------------------

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

    def _busy(self, busy: bool) -> None:
        inp = self.query_one("#cmd", Input)
        inp.disabled = busy
        if busy:
            inp.border_title = "…the table is thinking…"
            self.sub_title = "⏳ the table is thinking…"
        else:
            self._sync_input()
            self.sub_title = "SETUP" if self.lc.phase == "setup" else f"{self.mode.upper()} mode"
            inp.focus()

    # -- game interaction (off the UI thread) -------------------------------

    async def _open(self) -> None:
        self._busy(True)
        if self.lc.phase == "setup":
            await self._open_setup()
            return
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
        if resumed:
            self._write("scene", "[$text-muted]— resuming the session in progress —[/]")
        self._write("scene", f"\n[$accent]DM[/]  {inline(scene)}")
        self._busy(False)

    # -- setup: the new-campaign conversation (phase == "setup") -------------

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
        when it changes, so the build shows progress instead of hanging silently."""
        stage = next((label for frag, label in self._SETUP_STAGES if frag in arg), None)
        if stage and stage != self._setup_stage:
            self._setup_stage = stage
            self._write("scene", f"[$text-muted]  ▸ {stage}…[/]")

    async def _open_setup(self) -> None:
        """Open a brand-new campaign: a guided conversation in the scene pane, with the
        dm's authoring streamed behind the screen for the whole setup."""
        screen = self.query_one("#screen", VerticalScroll)
        self._setup_hidden = screen.has_class("hidden")
        screen.remove_class("hidden")
        self._write("screen", "\n[b]— building the campaign —[/b]\n")
        self._setup_stage = None
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
        # tool calls drive a spoiler-free progress ticker in the scene (the full,
        # spoiler-bearing authoring stays behind the screen).
        activity = lambda name, arg: self.call_from_thread(self._setup_activity, name, arg)
        self._setup_tap = self.lc.setup_stream(stream, on_tool=activity)
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
        self.sub_title = "⏳ planning session 1…"
        self._write("scene", "\n[$warning]— campaign built · planning session 1 —[/]")
        self._write("screen", "\n[b]— planning session 1 —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._tick, key)
        stream = lambda s: self.call_from_thread(self._append, "screen", s)
        try:
            n = await asyncio.to_thread(self.lc.finish_setup, ticker, stream)
        except Exception as e:  # noqa: BLE001 — surface any failure to the player
            self._write("scene", f"\n[$error]— setup failed: {escape(str(e))} —[/]")
            self._busy(False)
            return
        if self._setup_hidden:
            self.query_one("#screen", VerticalScroll).add_class("hidden")
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
        try:
            tr = await asyncio.to_thread(self.game.turn, text)
        except BackendCancelled:
            await self._cancel_cleanup(text)
            return
        self._render_dm(tr)
        self._render_gate(tr)
        self._busy(False)

    async def _do_meta(self, question: str) -> None:
        self._busy(True)
        try:
            answer = await asyncio.to_thread(self.game.meta, question)
        except BackendCancelled:
            await self._cancel_cleanup(question)
            return
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

    _WRAP_LABELS = {
        "digest": "reading back the session",
        "assess": "taking stock of what happened",
        "feedback": "noting your feedback",
        "canon": "filing what's new in the world",
        "arcs": "advancing the story",
        "state": "updating where things stand",
        "propagation": "double-checking everything lines up",
        "prep": "prepping the next session",
    }

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
        self._busy(True)
        self.sub_title = "⏳ wrapping the session…"
        self._write("scene", "\n[$warning]— wrapping the session —[/]")
        # Reveal the behind-the-screen pane so the live pipeline stream is visible,
        # remembering whether it was hidden so we can restore that afterward (it stays
        # closed by default — the wrap just borrows it).
        screen = self.query_one("#screen", VerticalScroll)
        was_hidden = screen.has_class("hidden")
        screen.remove_class("hidden")
        self._write("screen", "\n[b]— post-session pipeline —[/b]\n")
        ticker = lambda key: self.call_from_thread(self._tick, key)
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

    def _tick(self, key: str) -> None:
        self._write("scene", f"[$text-muted]  ▸ {self._WRAP_LABELS.get(key, key)}…[/]")

    # -- rendering ----------------------------------------------------------

    def _render_dm(self, tr) -> None:
        self._write("scene", f"\n[$accent]DM[/]  {inline(tr.final)}")

    def _render_gate(self, tr) -> None:
        self._turn += 1
        g = tr.gate
        nv = "[$success]PASS[/]" if g.narrative.passed else "[$error]VIOLATIONS[/]"
        cv = "[$success]PASS[/]" if g.conduct.passed else "[$error]VIOLATIONS[/]"
        status = "[$warning]CORRECTED[/]" if tr.corrected else "[$success]clean[/]"
        self._write("screen", f"\n[b]turn {self._turn}[/b]  canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon")
        if not g.narrative.passed:
            self._write("screen", f"[$error]canon[/]\n{inline(g.narrative.report.strip())}")
        if not g.conduct.passed:
            self._write("screen", f"[$error]conduct[/]\n{inline(g.conduct.report.strip())}")

    # -- actions ------------------------------------------------------------

    def action_toggle_screen(self) -> None:
        self.query_one("#screen", VerticalScroll).toggle_class("hidden")

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
