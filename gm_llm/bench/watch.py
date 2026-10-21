"""
A bench batch behind the engine protocol — what `bench run --ui tui` watches.

The batch drives itself (`run_batch`); this only renders it. Each run's lifecycle is attached
as the run opens, and its turns render through the engine's own hooks, composed under
bench's bookkeeping by `BatchHooks` — so a watched run makes the same calls in the same order
as a headless one (design/frontends.md § Constraints). Nothing typed reaches a run: the only
commands on offer are `cancel` (which leaves no trace) and `shutdown`.
"""

from __future__ import annotations

import threading

from .. import __version__
from ..engine.core import PROTOCOL, Engine
from .runner import BatchHooks


class BatchEngine(Engine):
    def __init__(self, drive):
        """`drive(hooks, note)` plays the batch — `run_batch` with its arguments bound."""
        super().__init__(None)
        self._drive = drive
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._emit("hello", protocol=PROTOCOL, version=__version__, directory="", batch=True)
        self._set(phase="play", busy="preparing the batch")
        self._thread = threading.Thread(target=self._run, name="bench-batch")
        self._thread.start()

    def actions(self) -> list[str]:
        if self.phase == "closed":
            return []
        return ["shutdown", "cancel"] if self.busy and self._loop_live else ["shutdown"]

    def close(self) -> None:
        """Stop the run in flight — it ends `incomplete`, resumable — and wait for the batch
        to unwind far enough to stop its backend and write its manifest line."""
        with self._lock:
            if self.phase == "closed":
                return
            self._closing = True
            self._release_loop()
        if self._thread is not None:
            self._thread.join()
        with self._lock:
            self._stop_tap()
            self._set(phase="closed", awaiting=None, busy=None)

    def _player(self) -> str:
        return "auto"

    def _context(self) -> None:
        pass  # a readout the archive can't see would make a watched run differ

    def _run(self) -> None:
        hooks = BatchHooks(on_run=self._on_run, on_open=self._on_open,
                           on_stage=lambda key: self._stage("wrap", key),
                           on_close=self._on_close)
        try:
            self._drive(hooks, self._note)
        except Exception as e:  # noqa: BLE001 — surface any failure to the watcher
            self._error("the batch", e)
        self._emit("batch", event="done")
        self._set(busy=None)

    def _note(self, msg: str) -> None:
        self._stream("note", f"[bench] {msg}\n")

    def _on_run(self, index: int, total: int, run_id: str) -> None:
        self._emit("batch", event="run", index=index, total=total, run=run_id)
        self._set(busy="assembling the run")

    def _on_open(self, lifecycle, source, scene: str):
        """Attach this run and hand back the hooks its turns render through. The source is
        the run's own — two sources would mean two players."""
        with self._lock:
            self.lc, self._source, self._loop_live, self._turn = lifecycle, source, True, 0
            lifecycle.backend.on_retry = self._retry
            if lifecycle.game is not None:
                lifecycle.game.on_step = self._step
            self._tap = lifecycle.play_stream(self._stream)
        self._say("dm", scene)
        return self._hooks()

    def _on_close(self, record: dict) -> None:
        with self._lock:
            self._loop_live = False
            self._stop_tap()
            self.lc, self._source = None, None
        self._emit("batch", event="close", record=record)
        self._set(busy=None)
