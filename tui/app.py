"""
PlayApp — the rich-TUI front-end over the orchestrator `Game`.

Layout: a scene pane (the play — DM narration + your lines), a toggleable
behind-the-screen pane (per-turn gate verdicts), and an input that switches
between ACTION mode (gated turn) and META mode (out-of-game question, ungated).

Model calls block, so they run off the UI thread (`asyncio.to_thread`) with the
input disabled while a turn resolves. The app talks only to a Game-like object
(`start`/`turn`/`meta` → TurnResult), so the same UI runs against MockGame or the
real backend.
"""

from __future__ import annotations

import asyncio

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, RichLog


class PlayApp(App):
    CSS = """
    #scene  { width: 2fr; border: round $primary;  padding: 0 1; }
    #screen { width: 1fr; border: round $warning;  padding: 0 1; }
    #screen.hidden { display: none; }
    #cmd { dock: bottom; border: tall $accent; }
    #cmd:disabled { border: tall $surface; }
    """

    BINDINGS = [
        ("ctrl+g", "toggle_screen", "Behind-screen"),
        ("ctrl+t", "toggle_mode", "Action/Meta"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, game, cleanup=None):
        super().__init__()
        self.game = game
        self.cleanup = cleanup
        self.mode = "action"
        self._turn = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield RichLog(id="scene", wrap=True, markup=True)
            yield RichLog(id="screen", wrap=True, markup=True)
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#screen", RichLog).write("[bold]behind the screen[/bold] — gate verdicts")
        self._sync_input()
        self.run_worker(self._open(), exclusive=True)

    # -- input mode ---------------------------------------------------------

    def _sync_input(self) -> None:
        inp = self.query_one("#cmd", Input)
        if self.mode == "action":
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
        else:
            self._sync_input()
            inp.focus()

    # -- game interaction (off the UI thread) -------------------------------

    async def _open(self) -> None:
        self._busy(True)
        tr = await asyncio.to_thread(self.game.start)
        self._render_dm(tr)
        self._busy(False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        scene = self.query_one("#scene", RichLog)
        if self.mode == "action":
            scene.write(f"\n[bold green]You[/bold green]  {escape(text)}")
            self.run_worker(self._do_turn(text), exclusive=True)
        else:
            scene.write(f"\n[dim]You (out-of-game)  {escape(text)}[/dim]")
            self.run_worker(self._do_meta(text), exclusive=True)

    async def _do_turn(self, text: str) -> None:
        self._busy(True)
        tr = await asyncio.to_thread(self.game.turn, text)
        self._render_dm(tr)
        self._render_gate(tr)
        self._busy(False)

    async def _do_meta(self, question: str) -> None:
        self._busy(True)
        answer = await asyncio.to_thread(self.game.meta, question)
        self.query_one("#scene", RichLog).write(f"[dim]DM (out-of-game)  {escape(answer)}[/dim]")
        self._busy(False)

    # -- rendering ----------------------------------------------------------

    def _render_dm(self, tr) -> None:
        self.query_one("#scene", RichLog).write(f"\n[bold cyan]DM[/bold cyan]  {escape(tr.final)}")

    def _render_gate(self, tr) -> None:
        self._turn += 1
        g = tr.gate
        screen = self.query_one("#screen", RichLog)
        nv = "[green]PASS[/green]" if g.narrative.passed else "[red]VIOLATIONS[/red]"
        cv = "[green]PASS[/green]" if g.conduct.passed else "[red]VIOLATIONS[/red]"
        status = "[yellow]CORRECTED[/yellow]" if tr.corrected else "[green]clean[/green]"
        screen.write(f"\n[bold]turn {self._turn}[/bold]  canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon")
        if not g.narrative.passed:
            screen.write(f"[red]canon[/red]\n{escape(g.narrative.report.strip())}")
        if not g.conduct.passed:
            screen.write(f"[red]conduct[/red]\n{escape(g.conduct.report.strip())}")

    # -- actions ------------------------------------------------------------

    def action_toggle_screen(self) -> None:
        self.query_one("#screen", RichLog).toggle_class("hidden")

    def action_toggle_mode(self) -> None:
        self.mode = "meta" if self.mode == "action" else "action"
        self._sync_input()

    async def on_unmount(self) -> None:
        if self.cleanup:
            self.cleanup()
