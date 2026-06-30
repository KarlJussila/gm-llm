"""
Campaign lifecycle — play a session, wrap it (reconcile + prep the next), play the
next, all from one front-end. Backend-agnostic: the caller (the TUI) supplies
callbacks for the between-sessions progress ticker and the live model stream.

`Game` (loop.py) owns live play; `Reconciler` owns the post-session pipeline. This
ties them into one moving object the UI can drive: `wrap()` reconciles the just-played
session and rolls `self.game` forward to the next, so the screen never leaves the app.
"""

from __future__ import annotations

from .loop import Game
from .reconciler import Reconciler
from .stream import EventTap


class Lifecycle:
    def __init__(self, backend, gate, directory: str, checks_log: str | None = None):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.checks_log = checks_log
        self.game = Game(backend, gate, checks_log=checks_log)

    @property
    def session(self) -> int:
        return self.game.session

    def wrap(self, on_stage=None, stream_write=None, commit: bool = True) -> int:
        """Reconcile the just-played session (digest → … → prep N+1), then roll the
        game forward to session N+1; returns the new session number.

        `on_stage(key)` fires as each pipeline stage starts (drives the ticker);
        `stream_write(text)` receives the live model output via an EventTap (drives the
        behind-the-screen pane). Both are called from worker/daemon threads."""
        n = self.game.session
        # markup=True: the stream sink is the Textual pane, which renders console
        # markup — EventTap colours headings/tools/reasoning and escapes body text.
        tap = (EventTap(self.backend.base, self.backend.directory, write=stream_write, markup=True).start()
               if stream_write else None)
        try:
            Reconciler(self.backend, self.gate, on_stage=on_stage,
                       checks_log=self.checks_log).reconcile_session(n, commit=commit)
        finally:
            if tap:
                tap.stop()
        self.game = Game(self.backend, self.gate, checks_log=self.checks_log, session=n + 1)
        return n + 1
