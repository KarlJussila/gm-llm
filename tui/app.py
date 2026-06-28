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
        self._scene: list[str] = []
        self._screen: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="scene"):
                yield Static(id="scene-body", markup=True)
            with VerticalScroll(id="screen"):
                yield Static(id="screen-body", markup=True)
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self._write("screen", "[bold]behind the screen[/bold] — gate verdicts")
        self._write("scene", "[dim]ctrl+t action/meta · ctrl+g behind-screen · /roll 2d6+3 · /meta <q>[/dim]")
        self._sync_input()
        self.sub_title = "ACTION mode"
        self.run_worker(self._open(), exclusive=True)

    # -- panes (selectable Statics) ----------------------------------------

    def _write(self, pane: str, markup: str) -> None:
        lines = self._scene if pane == "scene" else self._screen
        lines.append(markup)
        self.query_one(f"#{pane}-body", Static).update("\n".join(lines))
        self.query_one(f"#{pane}", VerticalScroll).scroll_end(animate=False)

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
            self.sub_title = "⏳ the table is thinking…"
        else:
            self._sync_input()
            self.sub_title = f"{self.mode.upper()} mode"
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

        # /roll — a local dice helper; doesn't take a turn, just shows the result
        # so you can report it in your next action.
        if text.lower().startswith("/roll"):
            result = roll_expr(text[5:].strip())
            self._write("scene", f"\n[yellow]{result or 'could not parse — try /roll 2d6+3'}[/yellow]")
            return
        # /meta — an out-of-game question without switching modes.
        if text.lower().startswith("/meta"):
            q = text[5:].strip()
            if q:
                self._write("scene", f"\n[dim]You (out-of-game)  {escape(q)}[/dim]")
                self.run_worker(self._do_meta(q), exclusive=True)
            return

        if self.mode == "action":
            self._write("scene", f"\n[bold green]You[/bold green]  {escape(text)}")
            self.run_worker(self._do_turn(text), exclusive=True)
        else:
            self._write("scene", f"\n[dim]You (out-of-game)  {escape(text)}[/dim]")
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
        self._write("scene", f"[dim]DM (out-of-game)  {escape(answer)}[/dim]")
        self._busy(False)

    # -- rendering ----------------------------------------------------------

    def _render_dm(self, tr) -> None:
        self._write("scene", f"\n[bold cyan]DM[/bold cyan]  {escape(tr.final)}")

    def _render_gate(self, tr) -> None:
        self._turn += 1
        g = tr.gate
        nv = "[green]PASS[/green]" if g.narrative.passed else "[red]VIOLATIONS[/red]"
        cv = "[green]PASS[/green]" if g.conduct.passed else "[red]VIOLATIONS[/red]"
        status = "[yellow]CORRECTED[/yellow]" if tr.corrected else "[green]clean[/green]"
        self._write("screen", f"\n[bold]turn {self._turn}[/bold]  canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon")
        if not g.narrative.passed:
            self._write("screen", f"[red]canon[/red]\n{escape(g.narrative.report.strip())}")
        if not g.conduct.passed:
            self._write("screen", f"[red]conduct[/red]\n{escape(g.conduct.report.strip())}")

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
