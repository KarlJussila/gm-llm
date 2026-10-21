"""
Campaign lifecycle — set up a new campaign, play a session, wrap it (reconcile + prep
the next), play the next, all from one object. Backend-agnostic: the caller (the engine)
supplies callbacks for the between-phases progress ticker and the live model stream.

`Setup` (setup.py) owns init, `Game` (loop.py) owns live play, `play_session` (play.py) owns
the turn loop over it, `Reconciler` owns the post-session pipeline. This ties them into one
moving object the engine drives:
  - an empty directory opens in the **setup** phase; `finish_setup()` plans session 1 and
    rolls into play(1);
  - `wrap()` reconciles the just-played session and rolls `self.game` to the next.
"""

from __future__ import annotations

from pathlib import Path

from ..settings import pull_feedback
from .packet import character_packet
from .paths import latest_session
from .loop import Game, session_is_complete
from .play import AgentPlayer, KeyboardPlayer, PlayerSource
from .reconciler import Reconciler
from .setup import Setup
from .status import CampaignStatus, campaign_status
from .stream import EventTap


class Lifecycle:
    def __init__(self, backend, gate, directory: str, logs=None,
                 player: str = "human"):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.logs = logs
        # Who supplies player turns (`--player`). The frontend asks for a source per session
        # and drives one loop either way — see `player_source`.
        self.player = player
        pull_feedback(directory)
        # Disk decides the opening phase: no session plan yet ⇒ a brand-new campaign
        # that needs setup; a session whose runner already signalled the end (even in
        # a prior run the player never confirmed the wrap on) ⇒ show that choice again,
        # never resume it into more play; otherwise jump straight into play.
        n = latest_session(Path(directory) / "campaign")
        if n is None:
            self.phase = "setup"
            self.game = None
            self.setup = Setup(backend, gate, directory, logs=logs)
        else:
            self.game = Game(backend, gate.preloader, logs=logs, session=n)
            self.setup = None
            self.phase = "wrap_pending" if session_is_complete(directory, n) else "play"

    @property
    def session(self) -> int:
        return self.game.session if self.game else 0

    def player_source(self, story: str | None = None) -> PlayerSource:
        """A fresh `PlayerSource` for the session about to be played — the axis `--player`
        selects, resolved here so a frontend never builds backend sessions of its own.

        **One per session loop, never reused.** A `KeyboardPlayer`'s `stop()` latches, and an
        `AgentPlayer` gets its own opencode session so the packet is re-handed (and the
        previous session's play isn't carried into the next one's context). `story` is what
        an `AgentPlayer` is told has happened before it starts."""
        if self.player != "auto":
            return KeyboardPlayer()
        return AgentPlayer(self.backend, self.backend.create_session("play-player"),
                           character=character_packet(Path(self.directory) / "campaign"),
                           story=story)

    def status(self) -> CampaignStatus:
        """Where the campaign stands — disk only (lint + git), no model calls.
        Blocking (subprocesses); the engine runs it on a thread of its own."""
        return campaign_status(self.directory)

    def _tap(self, stream, on_tool=None):
        """An EventTap handing the live model stream to `stream(kind, text)` (see
        `EventTap`), or None when no sink is wired. The caller stops it."""
        if not stream:
            return None
        return EventTap(self.backend, sink=stream, on_tool=on_tool).start()

    def setup_stream(self, stream, on_tool=None):
        """Stream setup's authoring for the whole conversation. `on_tool(name, arg)` fires
        per tool call — the engine turns it into spoiler-free progress labels."""
        return self._tap(stream, on_tool)

    def play_stream(self, stream):
        """Stream live model output for a session: turns, fights and meta questions."""
        return self._tap(stream)

    def finish_setup(self, on_stage=None, stream=None) -> int:
        """Once setup reports done: plan session 1 (the one code-gated artifact at init),
        then roll into play(1). Returns the new session number (1)."""
        if on_stage:
            on_stage("prep")
        tap = self._tap(stream)
        try:
            n = self.setup.finalize()
        finally:
            if tap:
                tap.stop()
        self.game = Game(self.backend, self.gate.preloader, logs=self.logs, session=n)
        self.phase = "play"
        self.setup = None
        return n

    def reconcile(self, n: int, on_stage=None, commit: bool = True) -> None:
        """The between-session pass over session `n` — the wrap's one expensive step,
        factored out so it can be stood in for. `bench run`'s no-opencode tests override
        this and nothing else, keeping the rest of the wrap (the warm-runner handoff
        notes, the roll forward) real rather than mocking the whole lifecycle."""
        Reconciler(self.backend, self.gate, on_stage=on_stage,
                   logs=self.logs).reconcile_session(n, commit=commit)

    def wrap(self, on_stage=None, stream=None, commit: bool = True) -> int:
        """Reconcile the just-played session (digest → … → prep N+1), then roll the
        game forward to session N+1; returns the new session number.

        `on_stage(key)` fires as each pipeline stage starts; `stream(kind, text)` receives
        the live model output. Both are called from worker/daemon threads."""
        n = self.game.session
        tap = self._tap(stream)
        try:
            # First, while the runner session is still warm, capture its handoff notes —
            # the between-session pipeline folds them in alongside the transcript.
            if on_stage:
                on_stage("handoff")
            self.game.handoff()
            self.reconcile(n, on_stage=on_stage, commit=commit)
        finally:
            if tap:
                tap.stop()
        self.game = Game(self.backend, self.gate.preloader, logs=self.logs, session=n + 1)
        self.phase = "play"  # the new session hasn't signalled an end yet
        return n + 1
