"""
A frontend's handle on an engine: `send` commands, read events off `events` (a queue).

Frontends import this module and nothing else of the engine's, so it must not import the
orchestrator. `ProcessClient` spawns `gm-llm serve` and speaks the protocol over its pipes;
`LocalClient` wraps an engine in this process (tests).
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading


class Client:
    def __init__(self):
        self.events: queue.Queue[dict] = queue.Queue()

    def send(self, cmd: dict) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class LocalClient(Client):
    """An `Engine` in this process. Starts it."""

    def __init__(self, engine):
        super().__init__()
        self._engine = engine
        engine.subscribe(self.events.put)
        engine.start()

    def send(self, cmd: dict) -> None:
        self._engine.send(cmd)

    def close(self) -> None:
        self._engine.close()


class ProcessClient(Client):
    """`python -m gm_llm <args>` in a child process — `serve …`, or `bench run --ui serve …`. The child gets its own process group, so
    the terminal's Ctrl+C reaches only the frontend, which turns it into a `cancel`. If the
    engine exits without closing, the client reports it and posts a `closed` state."""

    def __init__(self, args: list[str], *, stderr=None):
        super().__init__()
        group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                 else {"start_new_session": True})
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "gm_llm", *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            encoding="utf-8", bufsize=1, **group)
        self._lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        closed = False
        for line in self._proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            closed = closed or (ev.get("type") == "state" and ev.get("phase") == "closed")
            self.events.put(ev)
        if not closed:
            code = self._proc.wait()
            self.events.put({"type": "error", "what": "the engine",
                             "message": f"exited with code {code}"})
            self.events.put({"type": "state", "phase": "closed", "session": None,
                             "awaiting": None, "busy": None, "player": None,
                             "in_combat": False, "actions": []})

    def send(self, cmd: dict) -> None:
        with self._lock:
            try:
                self._proc.stdin.write(json.dumps(cmd) + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, ValueError, OSError):
                pass  # the engine is gone; the reader reports it

    def close(self, timeout: float = 30) -> None:
        """Ask the engine to shut down and wait for it; kill it if it won't go."""
        if self._proc.poll() is None:
            self.send({"type": "shutdown"})
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
