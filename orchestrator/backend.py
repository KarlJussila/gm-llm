"""
Backend client — the orchestrator's one connection to opencode.

Wraps a headless `opencode serve` (which loads the project's agents, skills, and
plugins) behind a tiny synchronous API: create a session, prompt an agent, get its
final text. All the throttle-handling the autoplay harness learned the hard way
lives here, in one place:

  - retry with backoff on errors, empty replies, and rate-limited *hangs*
    (a throttled call holds the connection open rather than erroring, so we cap
    the per-call timeout and treat a timeout as a retryable failure);
  - a minimum gap between calls, so the orchestrator doesn't burst the model's
    rate limit the way fan-out (runner + two checkers) did.

Backend-agnostic on purpose: the per-turn loop, the gate, and the interface all
talk to this, never to opencode directly.
"""

from __future__ import annotations

import json
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class BackendError(RuntimeError):
    pass


class Backend:
    def __init__(
        self,
        directory: str,
        port: int = 4181,
        turn_timeout: int = 360,
        retries: int = 6,
        min_call_gap: float = 1.0,
        serve_log: str = "/tmp/orchestrator-serve.log",
    ):
        self.directory = str(Path(directory).resolve())
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.turn_timeout = turn_timeout
        self.retries = retries
        self.min_call_gap = min_call_gap
        self.serve_log = serve_log
        self._proc: subprocess.Popen | None = None
        self._owns_server = False
        self._last_call = 0.0
        self.on_retry = None  # optional callback(agent, attempt, wait, reason)

    # -- server lifecycle ---------------------------------------------------

    def start(self, ready_timeout: int = 60) -> "Backend":
        """Boot our own `opencode serve` and wait until it answers."""
        log = open(self.serve_log, "w")
        self._proc = subprocess.Popen(
            ["opencode", "serve", "--port", str(self.port)],
            cwd=self.directory, stdout=log, stderr=subprocess.STDOUT,
        )
        self._owns_server = True
        self._wait_until_ready(ready_timeout)
        return self

    def attach(self) -> "Backend":
        """Use an already-running server on this port."""
        self._owns_server = False
        self._wait_until_ready(10)
        return self

    def stop(self) -> None:
        if self._proc and self._owns_server:
            try:
                self._proc.send_signal(signal.SIGINT)
                self._proc.wait(timeout=10)
            except Exception:
                self._proc.kill()
        self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()

    def _wait_until_ready(self, deadline_s: int) -> None:
        deadline = time.time() + deadline_s
        last = None
        while time.time() < deadline:
            try:
                self._raw_create({})
                return
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                last = e
                time.sleep(0.5)
        raise BackendError(f"server never came up on :{self.port}: {last}")

    # -- HTTP ---------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base}{path}?directory={urllib.parse.quote(self.directory)}"

    def _raw_post(self, path: str, body: dict, timeout: int) -> dict:
        req = urllib.request.Request(
            self._url(path), data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def _raw_get(self, path: str, timeout: int) -> dict:
        req = urllib.request.Request(self._url(path), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def _raw_create(self, body: dict) -> dict:
        return self._raw_post("/session", body, timeout=10)

    def _pace(self) -> None:
        gap = self.min_call_gap - (time.time() - self._last_call)
        if gap > 0:
            time.sleep(gap)
        self._last_call = time.time()

    @staticmethod
    def _last_text(resp: dict) -> str:
        parts = resp.get("parts", []) if isinstance(resp, dict) else []
        texts = [p.get("text", "") for p in parts if p.get("type") == "text" and p.get("text")]
        return texts[-1].strip() if texts else ""

    # -- public API ---------------------------------------------------------

    def create_session(self, title: str | None = None) -> str:
        sid = self._raw_create({"title": title} if title else {}).get("id")
        if not sid:
            raise BackendError("session create returned no id")
        return sid

    def session_valid(self, session_id: str) -> bool:
        """True if `session_id` still exists on the server (so a resume can reattach
        to it with its context intact). Fails *safe*: any error — a 404, a wrong
        endpoint, a hiccup — returns False, so the caller falls back to rebuilding
        from the transcript rather than reattaching to a dead session."""
        if not session_id:
            return False
        try:
            self._raw_get(f"/session/{session_id}/message", timeout=10)
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def prompt(self, session_id: str, agent: str, text: str) -> str:
        """Prompt `agent` on `session_id`; return its final text. Retries on
        failure/empty/timeout with backoff, paced to ease rate limits."""
        body = {"agent": agent, "parts": [{"type": "text", "text": text}]}
        for attempt in range(self.retries):
            self._pace()
            try:
                out = self._last_text(self._raw_post(f"/session/{session_id}/message", body, self.turn_timeout))
                if out:
                    return out
                reason = "empty reply (likely a rate-limited/errored stream)"
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:160] if hasattr(e, "read") else ""
                reason = f"HTTP {e.code} {detail}"
            except (urllib.error.URLError, OSError, ValueError) as e:
                reason = str(e)
            wait = min(15 * (2 ** attempt), 120)
            if self.on_retry:
                self.on_retry(agent, attempt + 1, wait, reason)
            time.sleep(wait)
        raise BackendError(f"{agent} failed after {self.retries} retries")
