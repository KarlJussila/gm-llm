"""
Campaign lifecycle — set up a new campaign, play a session, wrap it (reconcile + prep
the next), play the next, all from one front-end. Backend-agnostic: the caller (the TUI)
supplies callbacks for the between-phases progress ticker and the live model stream.

`Setup` (setup.py) owns init, `Game` (loop.py) owns live play, `Reconciler` owns the
post-session pipeline. This ties them into one moving object the UI can drive:
  - an empty directory opens in the **setup** phase; `finish_setup()` plans session 1 and
    rolls into play(1);
  - `wrap()` reconciles the just-played session and rolls `self.game` to the next.
So the screen never leaves the app across the whole campaign lifecycle.
"""

from __future__ import annotations

from pathlib import Path

from .loop import Game, _latest_session
from .reconciler import Reconciler
from .setup import Setup
from .stream import EventTap


class Lifecycle:
    def __init__(self, backend, gate, directory: str, logs=None):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.logs = logs
        # Disk decides the opening phase: no session plan yet ⇒ a brand-new campaign
        # that needs setup; otherwise jump straight into play.
        if _latest_session(Path(directory) / "campaign" / "sessions") is None:
            self.phase = "setup"
            self.game = None
            self.setup = Setup(backend, gate, directory, logs=logs)
        else:
            self.phase = "play"
            self.game = Game(backend, gate, logs=logs)
            self.setup = None

    @property
    def session(self) -> int:
        return self.game.session if self.game else 0

    def _tap(self, stream_write):
        """An EventTap routing the live model stream to the behind-the-screen pane —
        markup dialect for the Textual sink. None when no sink is wired."""
        if not stream_write:
            return None
        return EventTap(self.backend.base, self.backend.directory,
                        write=stream_write, markup=True).start()

    def setup_stream(self, stream_write, on_tool=None):
        """Stream the setup conversation's authoring behind the screen for its whole
        duration. The caller starts this when setup opens and stops it at the transition.
        `on_tool(name, arg)` fires per tool call — the TUI turns it into a spoiler-free
        progress ticker in the main scene."""
        if not stream_write:
            return None
        return EventTap(self.backend.base, self.backend.directory,
                        write=stream_write, markup=True, on_tool=on_tool).start()

    def play_stream(self, stream_write):
        """Stream live model output during a play turn or meta call. The caller
        starts this before the blocking call (so the stream is live for the
        whole turn — runner draft, checker tool calls, correction if any) and
        stops it when the call returns. Routes into the behind-the-screen pane;
        the pane stays closed by default — the stream accumulates so opening it
        mid-turn reveals what's happened so far. Returns the EventTap (or None
        if no sink is wired)."""
        return self._tap(stream_write)

    def finish_setup(self, on_stage=None, stream_write=None) -> int:
        """Once setup reports done: plan session 1 (the one code-gated artifact at init),
        then roll into play(1). Returns the new session number (1)."""
        if on_stage:
            on_stage("prep")
        tap = self._tap(stream_write)
        try:
            n = self.setup.finalize()
        finally:
            if tap:
                tap.stop()
        self.game = Game(self.backend, self.gate, logs=self.logs, session=n)
        self.phase = "play"
        self.setup = None
        return n

    def wrap(self, on_stage=None, stream_write=None, commit: bool = True) -> int:
        """Reconcile the just-played session (digest → … → prep N+1), then roll the
        game forward to session N+1; returns the new session number.

        `on_stage(key)` fires as each pipeline stage starts (drives the ticker);
        `stream_write(text)` receives the live model output via an EventTap (drives the
        behind-the-screen pane). Both are called from worker/daemon threads."""
        n = self.game.session
        tap = self._tap(stream_write)
        try:
            # First, while the runner session is still warm, capture its handoff notes —
            # the between-session pipeline folds them in alongside the transcript.
            if on_stage:
                on_stage("handoff")
            self.game.handoff()
            Reconciler(self.backend, self.gate, on_stage=on_stage,
                       logs=self.logs).reconcile_session(n, commit=commit)
        finally:
            if tap:
                tap.stop()
        self.game = Game(self.backend, self.gate, logs=self.logs, session=n + 1)
        return n + 1
