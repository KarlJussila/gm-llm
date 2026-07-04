"""
Modal screens for PlayApp — the Esc menu, the campaign-status view, and the
dice-roll prompt. Each is a thin `ModalScreen` that returns a value (or None)
to the app; all decisions about what a selection *does* stay in the app.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option


class _Modal(ModalScreen):
    """Shared chrome: Esc closes, clicking the dimmed backdrop closes."""

    BINDINGS = [("escape", "close", "Close")]

    DEFAULT_CSS = """
    _Modal { align: center middle; background: $background 60%; }
    _Modal > Vertical { width: 52; height: auto; max-height: 80%;
                        border: round $primary; background: $surface; padding: 1 2; }
    _Modal .modal-title { text-style: bold; color: $accent; margin: 0 0 1 0; }
    _Modal .modal-hint  { color: $text-muted; margin: 1 0 0 0; }
    """

    def action_close(self) -> None:
        self.dismiss(None)

    def on_click(self, event) -> None:
        # A click on the backdrop (the screen itself, not the dialog) closes.
        try:
            widget, _ = self.get_widget_at(event.screen_x, event.screen_y)
        except Exception:  # noqa: BLE001 — dismissal nicety, never break on it
            return
        if widget is self:
            self.dismiss(None)


class MenuScreen(_Modal):
    """The app menu: every player-facing action in one list, keybinds shown,
    items disabled when they don't apply right now. Returns the selected
    option id, or None."""

    DEFAULT_CSS = """
    MenuScreen OptionList { height: auto; background: transparent; border: none; padding: 0; }
    """

    def __init__(self, items: list[tuple[str, str, bool]]):
        """`items`: (option-id, label, disabled) — the app snapshots its state
        into this list, so the menu itself is stateless."""
        super().__init__()
        self._items = items

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Menu", classes="modal-title")
            yield OptionList(*[Option(label, id=oid, disabled=disabled)
                               for oid, label, disabled in self._items])
            yield Static("↑↓ + enter · esc to close", classes="modal-hint")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class StatusScreen(_Modal):
    """Where the campaign stands — a read-only render of a `CampaignStatus`
    snapshot (the same one `cli.py status` prints)."""

    DEFAULT_CSS = """
    StatusScreen > Vertical { width: 64; }
    StatusScreen .status-line { margin: 0; }
    StatusScreen .status-bad  { color: $error; }
    StatusScreen .status-good { color: $success; }
    """

    def __init__(self, st):
        super().__init__()
        self._st = st

    def compose(self) -> ComposeResult:
        st = self._st
        with Vertical():
            yield Static("Campaign status", classes="modal-title")
            phase = ("setup — no session planned yet" if st.session is None
                     else f"play · latest session: {st.session}")
            yield Static(f"[b]phase[/b]  {phase}", classes="status-line")
            if st.artifacts:
                marks = " · ".join(
                    f"[$success]{name} ✓[/]" if present else f"[$text-muted]{name} ✗[/]"
                    for name, present in st.artifacts)
                yield Static(f"[b]session {st.session}[/b]  {marks}", classes="status-line")
            if st.reconcile_stages:
                yield Static(f"[b]reconcile[/b]  {len(st.reconcile_stages)} stage(s) done "
                             f"({', '.join(st.reconcile_stages)})", classes="status-line")
            lint = f"[b]entities[/b]  {st.entities_complete}/{st.entities_total} complete (lint)"
            yield Static(lint, classes="status-line " +
                         ("status-bad" if st.incomplete else "status-good"))
            for path in st.incomplete[:5]:
                yield Static(f"  ✗ {path}", classes="status-line status-bad")
            if len(st.incomplete) > 5:
                yield Static(f"  … and {len(st.incomplete) - 5} more", classes="status-line")
            if st.git_state is not None:
                git = ("dirty (uncommitted campaign changes)" if st.git_state == "dirty"
                       else "clean")
                last = f' · last: "{st.last_commit}"' if st.last_commit else ""
                yield Static(f"[b]git[/b]  {git}{last}", classes="status-line")
            yield Static("esc to close", classes="modal-hint")


class RollScreen(_Modal):
    """Ask for a dice expression. Returns the expression string, or None on
    cancel. (Its own input, not the main bar — a draft may be sitting there.)"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Roll dice", classes="modal-title")
            yield Input(placeholder="e.g. 2d6+3, d20+7, 4d6+1d4", id="roll-expr")
            yield Static("enter to roll · esc to cancel", classes="modal-hint")

    def on_mount(self) -> None:
        self.query_one("#roll-expr", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()  # don't bubble into the app's play-bar handler
        expr = event.value.strip()
        self.dismiss(expr or None)
