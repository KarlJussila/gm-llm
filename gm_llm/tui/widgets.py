"""
Widgets for PlayApp — the scene's turn blocks, the working status bar, and the
phase-boundary prompt bar.

Every scene block is a `Static` subclass so the text stays selectable (the
reason the old single-string pane existed at all); the visual separation now
comes from one widget per beat instead of markup in a shared buffer. All
methods here run on the UI thread — workers reach them via `call_from_thread`.
"""

from __future__ import annotations

import time
from collections import Counter

from textual.message import Message
from textual.widgets import Static


class SceneLine(Static):
    """A one-line note in the scene flow — stage ticker entries, session rules,
    error notices. The `kind` picks the variant: status (muted, default),
    rule (warning banner), success, or error."""

    DEFAULT_CSS = """
    SceneLine { color: $text-muted; }
    SceneLine.rule    { color: $warning; margin: 1 0 0 0; text-style: bold; }
    SceneLine.success { color: $success; margin: 1 0 0 0; text-style: bold; }
    SceneLine.error   { color: $error;   margin: 1 0 0 0; text-style: bold; }
    """

    def __init__(self, text: str, kind: str = "status", **kwargs):
        classes = kwargs.pop("classes", "") or ""
        super().__init__(text, classes=f"{classes} {kind}".strip(), **kwargs)


class PlayerLine(Static):
    """The player's line — what your character does (or, with `meta`, an
    out-of-game question). A thick side rule marks the speaker."""

    DEFAULT_CSS = """
    PlayerLine { margin: 1 0 0 0; padding: 0 1; border-left: thick $success; }
    PlayerLine.meta { border-left: thick $panel; color: $text-muted; }
    """

    def __init__(self, markup_text: str, meta: bool = False, **kwargs):
        super().__init__(markup_text, classes="meta" if meta else None, **kwargs)


class DMBlock(Static):
    """One DM narration beat. The gate's verdict attaches to the block itself
    as a border subtitle (`✓ checked` / `✎ corrected (…)`), so the check that
    guarded a beat is visually part of that beat."""

    DEFAULT_CSS = """
    DMBlock {
        margin: 1 0 0 0; padding: 0 1;
        border: round $surface-lighten-2;
        border-title-color: $accent;
        border-subtitle-color: $text-muted;
    }
    DMBlock.meta { color: $text-muted; border: round $surface; }
    """

    def __init__(self, markup_text: str, meta: bool = False, **kwargs):
        super().__init__(markup_text, classes="meta" if meta else None, **kwargs)
        self.border_title = "DM (out-of-game)" if meta else "DM"

    def set_gate(self, corrected: bool, fixed: list[str]) -> None:
        self.border_subtitle = (
            f"✎ corrected ({' + '.join(fixed) or 'gate'}) — ctrl+g for details"
            if corrected else "✓ checked")


class PendingBlock(Static):
    """Stands in for the DM block while the turn resolves; the app removes it
    when the narration lands (or the turn is cancelled)."""

    DEFAULT_CSS = """
    PendingBlock { margin: 1 0 0 0; padding: 0 1; color: $text-muted; text-style: italic; }
    """

    def __init__(self, label: str = "the DM is thinking", **kwargs):
        super().__init__(f"┄┄ {label} ┄┄", **kwargs)


class StatusBar(Static):
    """One docked row of live progress while the table works: a phase label,
    the trail of phases already passed this wait, and the elapsed clock —
    `● checking canon & conduct  ·  the DM is writing ▸  ·  0:42`. Hidden when
    idle. `note()` overlays a transient warning (backend retries) that clears
    back to the phase line on its own.

    The elapsed clock deliberately survives `start()` re-entry (a turn that
    rolls into a wrap is one continuous wait), matching the old heartbeat."""

    DEFAULT_CSS = """
    StatusBar { height: 1; padding: 0 1; background: $boost; color: $text-muted;
                display: none; }
    StatusBar.active { display: block; }
    StatusBar.warn   { color: $warning; }
    """

    _TRAIL_MAX = 3  # most recent passed phases shown; older ones fall off the left

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._t0: float | None = None
        self._phase: str | None = None
        self._trail: list[str] = []
        self._timer = None
        self._note_timer = None
        self._warn: str | None = None  # a sticky warning (backend retries), cleared on progress

    def start(self, title: str) -> None:
        if self._t0 is None:  # don't reset the clock on re-entry — the wait is continuous
            self._t0 = time.monotonic()
            self._trail = []
        self._phase = title
        self.add_class("active")
        if self._timer is None:
            self._timer = self.set_interval(1, self._render_line)
        self._render_line()

    def set_phase(self, label: str) -> None:
        if self._phase and self._phase != label:
            self._trail.append(self._phase)
        self._phase = label
        self._clear_warn()  # reaching a new phase means the stuck call recovered
        self._render_line()

    def note(self, text: str, sticky: bool = False) -> None:
        """A warning over the phase line. Transient by default (clears after a few
        seconds); `sticky` keeps it up — with the running clock — until the next phase
        transition clears it, so a run of backend retries stays plainly on screen the
        whole time a call is stuck instead of flickering past between attempts."""
        if self._note_timer is not None:
            self._note_timer.stop()
            self._note_timer = None
        self.add_class("warn")
        if sticky:
            self._warn = text
            self._render_line()
        else:
            self._warn = None
            self.update(text)
            self._note_timer = self.set_timer(6, self._clear_note)

    def _clear_note(self) -> None:
        self._note_timer = None
        self.remove_class("warn")
        self._render_line()

    def _clear_warn(self) -> None:
        if self._warn is not None:
            self._warn = None
            self.remove_class("warn")

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._note_timer is not None:
            self._note_timer.stop()
            self._note_timer = None
        self._t0 = None
        self._phase = None
        self._trail = []
        self._warn = None
        self.remove_class("active")
        self.remove_class("warn")
        self.update("")

    def _render_line(self) -> None:
        if self._t0 is None or self._note_timer is not None:
            return
        m, s = divmod(int(time.monotonic() - self._t0), 60)
        if self._warn is not None:
            self.update(f"[$warning]⚠[/] {self._warn}  ·  {m}:{s:02d}")
            return
        trail = " ▸ ".join(self._trail[-self._TRAIL_MAX:])
        parts = [f"[$warning]●[/] {self._phase}"]
        if trail:
            parts.append(f"[$text-disabled]{trail} ▸[/]")
        parts.append(f"{m}:{s:02d}")
        self.update("  ·  ".join(parts))


class BatchHeader(Static):
    """The batch chrome: which run of how many is playing, and how the finished ones went —
    `bench  run 2/5 · run-20260728T…  ·  1 complete`.

    The one thing no per-session widget can say. A batch outlives every lifecycle the app
    attaches (design/frontends.md step 4), so the tally lives here rather than being
    re-derived from a campaign that is only the current run's. Hidden unless the app is
    watching a batch.

    Outcomes are tallied by their head word — `incomplete: rate limited` and
    `incomplete: stopped from the frontend` are one column, not two."""

    DEFAULT_CSS = """
    BatchHeader { height: 1; padding: 0 1; background: $primary 20%; color: $text;
                  display: none; }
    BatchHeader.active { display: block; }
    """

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._label = "preparing the batch…"
        self._outcomes: list[str] = []
        self._line = ""

    @property
    def line(self) -> str:
        """What the header currently says (markup and all) — the batch's own summary of
        itself, readable without reaching into Textual's render internals."""
        return self._line

    def activate(self) -> None:
        self.add_class("active")
        self._render_line()

    def set_run(self, index: int, total: int, run_id: str) -> None:
        self._label = f"run {index}/{total} · {run_id}"
        self._render_line()

    def set_outcome(self, outcome: str) -> None:
        self._outcomes.append(str(outcome).split(":")[0].strip())
        self._render_line()

    def set_done(self) -> None:
        self._label = "batch done"
        self._render_line()

    def _render_line(self) -> None:
        tally = Counter(self._outcomes)
        so_far = "  ·  ".join(f"{n} {name}" for name, n in tally.most_common())
        self._line = f"[b]bench[/b]  {self._label}" + (f"  ·  {so_far}" if so_far else "")
        self.update(self._line)


class PromptBar(Static, can_focus=True):
    """The phase-boundary yes/no: a highlighted row above the input asking to
    trigger the next phase (wrap the session / start session 1). Focus-based —
    `ask()` takes focus so y/n/enter/esc answer it; the Yes/No spans are
    clickable for mouse users. Dismissing restores focus to whoever had it.

    Answers surface as a posted `PromptBar.Answered(value)`; the app decides
    what the answer triggers (the bar knows nothing about phases)."""

    class Answered(Message):
        def __init__(self, value: bool) -> None:
            self.value = value
            super().__init__()

    BINDINGS = [
        ("y,enter", "yes", "Yes"),
        ("n,escape", "no", "Not yet"),
    ]

    DEFAULT_CSS = """
    PromptBar { height: 3; padding: 0 1; content-align: left middle; display: none;
                border: tall $warning; background: $warning 15%; color: $text; }
    PromptBar.active { display: block; }
    PromptBar:focus { background: $warning 25%; }
    """

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._return_focus = None

    @property
    def active(self) -> bool:
        return self.has_class("active")

    def ask(self, message: str) -> None:
        self._return_focus = self.app.focused
        self.update(f"▶ {message}   "
                    f"[bold][@click=yes]\\[Y]es[/][/] / [bold][@click=no]\\[N]ot yet[/][/]")
        self.add_class("active")
        self.focus()

    def dismiss(self) -> None:
        """Hide without answering (the pending action was triggered elsewhere,
        e.g. ctrl+w or the menu)."""
        if self.active:
            self._hide()

    def action_yes(self) -> None:
        self._answer(True)

    def action_no(self) -> None:
        self._answer(False)

    def _answer(self, value: bool) -> None:
        if not self.active:
            return
        self._hide()
        self.post_message(self.Answered(value))

    def _hide(self) -> None:
        self.remove_class("active")
        target, self._return_focus = self._return_focus, None
        if target is not None and target.is_attached:
            target.focus()
