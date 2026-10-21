"""
Backend client — the orchestrator's one connection to opencode.

Wraps a headless `opencode serve` (opencode 2.x, which loads the project's agents, skills, and
plugins) behind a tiny synchronous API: create a session, prompt an agent, get its reply. The v2
server takes a prompt into the session's inbox and runs it asynchronously, so a call here is:
send the prompt, block until the session goes idle, then read the turn back from the session's
messages. All the throttle-handling the autoplay harness learned the hard way lives here too:

  - retry with backoff on errors, empty replies, and rate-limited *hangs* (a throttled call
    simply stops producing output; a liveness tap on the event stream notices when nothing has
    arrived for `stall_timeout` seconds and interrupts that attempt as a retryable stall);
  - a minimum gap between calls, so the orchestrator doesn't burst the model's rate limit.

Backend-agnostic on purpose: the loop, the gates, and the interfaces talk to this, never to
opencode directly.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .logs import Logs, append


@dataclass(frozen=True)
class Reply:
    """A prompt's result: the agent's text, the set of tool names it called this turn, and
    their input args. `tools` lets a caller detect an explicit signal the model raised via a
    tool (e.g. `task_complete`) without prose-parsing. `tool_inputs` maps each tool name to its
    input dict (last call wins if called twice), so a caller can read structured fields — e.g.
    the `report_findings` tool's `passed` and `report`."""
    text: str
    tools: frozenset[str] = field(default_factory=frozenset)
    tool_inputs: dict[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextUsage:
    """A session's live context footprint: the tokens its last model call sent, against the
    model's usable input ceiling (its input cap if it advertises one, else its context window)."""
    tokens: int
    context_limit: int

    @property
    def pct(self) -> float:
        return (self.tokens / self.context_limit * 100) if self.context_limit else 0.0


class BackendError(RuntimeError):
    pass


class BackendCancelled(BackendError):
    """The in-flight call was cancelled via `abort()` (e.g. the player hit the cancel key after
    a mistype). Raised instead of returning a partial/empty reply or retrying, so the turn
    unwinds cleanly before anything is committed."""
    pass


# The stall budget for reconcile/handoff calls (via `Backend.patient()`): they read whole
# transcripts, so their prefill emits nothing for a long time and a working first token can be
# many minutes out. Set at half reconcile's ~30-min hard `turn_timeout` — room for a genuinely
# slow first token, while a call that's truly dead still gives up well before the backstop.
HEAVY_STALL_TIMEOUT = 900

# …and fewer retries for those heavy calls: a throttled heavy call burns the full stall budget
# every attempt with nothing to show, so two attempts give one genuinely-slow call its long
# chance, then give up and let a resume pick it up when the caps clear.
HEAVY_RETRIES = 2

# opencode's v2 server takes HTTP basic auth with this fixed user and a per-server password.
_USER = "opencode"

# Server config for the processes we own. Auto-compaction is opencode's single, lossy
# summarisation pass over a long session — exactly the model-judgment rewrite this pipeline
# avoids everywhere else — so it stays off; a session that runs long is the DM's to close.
_SERVER_CONFIG = {"compaction": {"auto": False}}


class Backend:
    def __init__(
        self,
        directory: str,
        port: int = 4181,
        turn_timeout: int = 360,
        retries: int = 4,
        min_call_gap: float = 1.0,
        stall_timeout: int = 180,
        logs: Logs | None = None,
    ):
        self.directory = str(Path(directory).resolve())
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        # The server's password: ours when we start it, the environment's when we attach.
        self.password = os.environ.get("OPENCODE_SERVER_PASSWORD") or secrets.token_urlsafe(24)
        # `turn_timeout` is the hard backstop; the stall watchdog normally fires first.
        self.turn_timeout = turn_timeout
        self.retries = retries
        self.min_call_gap = min_call_gap
        # A call that produces no stream activity for this long has stalled — a rate limit, or
        # a first token that never came — so interrupt and retry rather than block to the full
        # `turn_timeout`. A productive call keeps streaming (text, reasoning and tool events),
        # so this only fires on a genuine gap.
        self.stall_timeout = stall_timeout
        self._stall_override: int | None = None    # `patient()` raises the budget for heavy calls
        self._retries_override: int | None = None  # …and can lower the retry count for them
        self._stall_poll = 5.0  # how often the watchdog checks the liveness clock
        self.logs = logs or Logs.under(project=self.directory)
        self._proc: subprocess.Popen | None = None
        self._owns_server = False
        self._last_call = 0.0
        # Liveness: a background tap on the event stream bumps `_last_activity` on every
        # session event, so the stall watchdog can tell a hung call from a slow one.
        self._last_activity = 0.0
        self._stalled = False
        self._live_stop = threading.Event()
        self._live_thread: threading.Thread | None = None
        # Cancellation: `abort()` (any thread) sets the event and interrupts the session parked
        # in `_inflight_sid`; the running call sees the event and raises BackendCancelled.
        self._cancel = threading.Event()
        self._inflight_sid: str | None = None
        self.on_retry = None  # optional callback(agent, attempt, wait, reason)
        self._agents: dict[str, str] = {}       # session id -> the agent it's switched to
        self._agent_models: dict[str, dict | None] = {}  # agent -> its pinned model
        self._models: list[dict] | None = None  # /model, fetched once (static catalog)

    # -- server lifecycle ---------------------------------------------------

    def start(self, ready_timeout: int = 60) -> "Backend":
        """Boot our own `opencode serve` and wait until it answers."""
        log = open(self.logs.serve, "w")
        exe = shutil.which("opencode") or "opencode"
        env = {**os.environ, "OPENCODE_SERVER_PASSWORD": self.password,
               "OPENCODE_CONFIG_CONTENT": json.dumps(_SERVER_CONFIG)}
        if os.name == "nt":
            # From `npm i -g`, `opencode` is an `opencode.cmd` shim that CreateProcess can't
            # launch directly, so run it through the shell. A new process group isolates it
            # from the TUI's console signals; stop() reaps the whole tree with taskkill.
            self._proc = subprocess.Popen(
                f'"{exe}" serve --port {self.port}',
                cwd=self.directory, stdout=log, stderr=subprocess.STDOUT, env=env,
                shell=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            self._proc = subprocess.Popen(
                [exe, "serve", "--port", str(self.port)],
                cwd=self.directory, stdout=log, stderr=subprocess.STDOUT, env=env,
            )
        self._owns_server = True
        self._wait_until_ready(ready_timeout)
        self._start_liveness()
        return self

    def attach(self) -> "Backend":
        """Use an already-running server on this port (its password from
        `OPENCODE_SERVER_PASSWORD`)."""
        self._owns_server = False
        self._wait_until_ready(10)
        self._start_liveness()
        return self

    def stop(self) -> None:
        self._live_stop.set()
        if self._proc and self._owns_server:
            try:
                if os.name == "nt":
                    # The server sits under a cmd.exe shim; taskkill /T force-kills the whole
                    # tree (shell + opencode + its children) without cmd's Y/N prompt.
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                                   capture_output=True)
                else:
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
                self._request("GET", "/info", timeout=5)
                return
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                last = e
                time.sleep(0.5)
        raise BackendError(f"server never came up on :{self.port}: {last}")

    # -- HTTP ---------------------------------------------------------------

    def _open(self, method: str, path: str, body: dict | None = None, timeout: float | None = None):
        """An authenticated request to the v2 API; the raw response, for streaming."""
        token = base64.b64encode(f"{_USER}:{self.password}".encode()).decode()
        headers = {"Authorization": f"Basic {token}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base}/api{path}", data=data, headers=headers,
                                     method=method)
        return urllib.request.urlopen(req, timeout=timeout)

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: float = 30) -> dict | None:
        """An authenticated JSON request; the decoded body, or None for an empty one."""
        with self._open(method, path, body, timeout) as r:
            raw = r.read()
        return json.loads(raw.decode()) if raw else None

    def open_events(self):
        """The server's event stream (SSE) — for the liveness tap and the live `EventTap`."""
        return self._open("GET", "/event")

    def session_title(self, session_id: str) -> str | None:
        try:
            return ((self._request("GET", f"/session/{session_id}", timeout=5) or {})
                    .get("data") or {}).get("title")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    # -- liveness -----------------------------------------------------------

    def _start_liveness(self) -> None:
        """Watch the event stream in the background and stamp `_last_activity` on every
        session event — the signal the stall watchdog reads. Headless, so bench runs get stall
        detection with no UI attached. Prompts are serialized, so any session activity during
        a call belongs to that call."""
        self._last_activity = time.time()
        self._live_stop.clear()
        self._live_thread = threading.Thread(target=self._liveness_run, daemon=True)
        self._live_thread.start()

    def _liveness_run(self) -> None:
        while not self._live_stop.is_set():
            try:
                with self.open_events() as resp:  # streaming; lives as long as the server
                    for raw in resp:
                        if self._live_stop.is_set():
                            return
                        if b'"type":"session.' in raw:
                            self._last_activity = time.time()
            except Exception:  # noqa: BLE001 — stream dropped/server gone; reconnect
                if self._live_stop.is_set():
                    return
                time.sleep(1)

    def _effective_stall(self) -> int:
        """The stall budget in force: the `patient()` override if set, else `stall_timeout`."""
        return self._stall_override or self.stall_timeout

    def _effective_retries(self) -> int:
        """The retry count in force: the `patient()` override if set, else `retries`."""
        return self._retries_override or self.retries

    @contextmanager
    def patient(self, stall_timeout: int, retries: int | None = None):
        """Widen the stall budget (and optionally lower the retry count) for a block of heavy
        calls — reconcile and handoff read whole transcripts, so their time-to-first-token
        dwarfs a play turn's. Prompts are serialized, so single override attributes are safe;
        nested calls restore the outer values on exit."""
        prev_stall, prev_retries = self._stall_override, self._retries_override
        self._stall_override = stall_timeout
        self._retries_override = retries
        try:
            yield
        finally:
            self._stall_override, self._retries_override = prev_stall, prev_retries

    def _pace(self) -> None:
        gap = self.min_call_gap - (time.time() - self._last_call)
        if gap > 0:
            time.sleep(gap)
        self._last_call = time.time()

    # -- one exchange ---------------------------------------------------------

    def _use_agent(self, session_id: str, agent: str) -> None:
        """A v2 session runs one agent at a time; switch it when the caller names another.
        Switching the agent leaves the session on whatever model it had, so the agent's own
        pinned model (and reasoning variant) is set alongside it."""
        if self._agents.get(session_id) == agent:
            return
        self._request("POST", f"/session/{session_id}/agent", {"agent": agent})
        model = self._agent_model(agent)
        if model:
            self._request("POST", f"/session/{session_id}/model", {"model": model})
        self._agents[session_id] = agent

    def _agent_model(self, agent: str) -> dict | None:
        """The model an agent file pins (`id`, `providerID`, `variant`), fetched once per agent."""
        if agent not in self._agent_models:
            info = (self._request("GET", f"/agent/{urllib.parse.quote(agent)}") or {}).get("data") or {}
            self._agent_models[agent] = info.get("model")
        return self._agent_models[agent]

    def _send(self, session_id: str, text: str) -> str:
        """Put a prompt in the session's inbox; the id of the user message it becomes."""
        return self._request("POST", f"/session/{session_id}/prompt", {"text": text})["data"]["id"]

    def _turn(self, session_id: str, user_id: str) -> list[dict]:
        """Every message the session holds after `user_id`, oldest first — this turn."""
        newer: list[dict] = []
        cursor = None
        while True:
            query = "?order=desc&limit=100" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
            page = self._request("GET", f"/session/{session_id}/message{query}") or {}
            for m in page.get("data") or []:
                if m.get("id") == user_id:
                    return newer[::-1]
                newer.append(m)
            cursor = (page.get("cursor") or {}).get("next")
            if not cursor:
                return newer[::-1]

    def _await_turn(self, session_id: str, user_id: str) -> list[dict]:
        """Block until the session goes idle after `user_id`; return the turn's messages.

        The wait is guarded by the stall watchdog: if no session activity arrives for the
        effective stall budget, it interrupts the session and sets `_stalled`, so the caller
        retries the attempt as a stall. `turn_timeout` is the hard backstop."""
        self._stalled = False
        self._last_activity = time.time()
        budget = self._effective_stall()
        deadline = time.time() + self.turn_timeout
        done = threading.Event()

        def watch() -> None:
            while not done.wait(self._stall_poll):
                if self._cancel.is_set():
                    return
                if time.time() - self._last_activity > budget or time.time() > deadline:
                    self._stalled = True
                    self._interrupt(session_id)
                    return

        threading.Thread(target=watch, daemon=True).start()
        try:
            while True:
                left = deadline - time.time()
                if left < -60:  # interrupted at the deadline, and still no end to the turn
                    raise TimeoutError(f"no reply within {self.turn_timeout}s")
                if left <= 0:
                    self._stalled = True
                    self._interrupt(session_id)
                try:
                    self._request("POST", f"/experimental/session/{session_id}/wait",
                                  timeout=max(left, 0) + 30)
                except (TimeoutError, urllib.error.URLError) as e:
                    if not isinstance(getattr(e, "reason", e), TimeoutError):
                        raise
                msgs = self._turn(session_id, user_id)
                if any(m.get("type") == "idle" for m in msgs):
                    return msgs
                time.sleep(0.5)  # the wait returned before the turn began; wait again
        finally:
            done.set()

    def _interrupt(self, session_id: str) -> None:
        try:
            self._request("POST", f"/session/{session_id}/interrupt", timeout=10)
        except (urllib.error.URLError, OSError, ValueError):
            pass  # best-effort; the wait still unwinds via the backstop

    def _exchange(self, session_id: str, agent: str, text: str, whole: bool) -> Reply:
        """Prompt `agent` on `session_id` and read the turn back, retrying on failure, empty
        replies, and stalls, with backoff and pacing. Cancellable: `abort()` from another
        thread raises BackendCancelled here rather than retrying or returning a partial reply."""
        self._cancel.clear()
        self._inflight_sid = session_id
        retries = self._effective_retries()
        try:
            for attempt in range(retries):
                self._pace()
                user_id = None
                try:
                    self._use_agent(session_id, agent)
                    user_id = self._send(session_id, text)
                    msgs = self._await_turn(session_id, user_id)
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    texts, calls, error = read_turn(msgs)
                    if self.logs.debug:
                        self._dump_turn(session_id, agent, msgs)
                    out = pick_text(texts, whole)
                    if self._stalled:
                        reason = f"no output for {self._effective_stall()}s (stalled — rate limit or slow first token)"
                    elif error:
                        reason = error
                    elif out or calls:
                        # A tool-call-only turn is a legitimate reply — e.g. a checker told to
                        # submit report_findings and output nothing else.
                        inputs: dict[str, dict] = {}
                        for name, inp in calls:
                            inputs[name] = inp  # last call wins (fine for signal tools)
                        return Reply(out, frozenset(inputs), inputs)
                    else:
                        reason = "empty reply (likely a rate-limited/errored stream)"
                except BackendCancelled:
                    raise
                except urllib.error.HTTPError as e:
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    detail = e.read().decode(errors="replace")[:160] if hasattr(e, "read") else ""
                    reason = f"HTTP {e.code} {detail}"
                except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    reason = str(e)
                # A failed attempt leaves its prompt in the session; take it back out so the
                # retry doesn't stack a second copy into the context.
                if user_id:
                    self._revert_to(session_id, user_id)
                wait = min(15 * (2 ** attempt), 120)
                if self.on_retry:
                    self.on_retry(agent, attempt + 1, wait, reason)
                if self._cancel.wait(wait):  # interruptible backoff — abort breaks the wait
                    raise BackendCancelled(f"{agent} call cancelled")
            raise BackendError(f"{agent} failed after {retries} retries")
        finally:
            self._inflight_sid = None

    def _dump_turn(self, session_id: str, agent: str, msgs: list[dict]) -> None:
        """Debug (logs.debug): append the turn's full message structure to the raw log."""
        block = (f"\n{'=' * 72}\n{datetime.now(timezone.utc).isoformat(timespec='seconds')}  "
                 f"agent={agent}  session={session_id}\n"
                 + json.dumps(msgs, ensure_ascii=False, indent=1) + "\n")
        append(self.logs.raw, block)

    # -- public API ---------------------------------------------------------

    def create_session(self, title: str | None = None) -> str:
        body: dict = {"location": {"directory": self.directory}}
        if title:
            body["title"] = title
        sid = ((self._request("POST", "/session", body, timeout=10) or {}).get("data") or {}).get("id")
        if not sid:
            raise BackendError("session create returned no id")
        return sid

    def session_valid(self, session_id: str) -> bool:
        """True if `session_id` still exists on the server (so a resume can reattach to it with
        its context intact). Fails safe: any error returns False, so the caller rebuilds from
        the transcript rather than reattaching to a dead session."""
        if not session_id:
            return False
        try:
            self._request("GET", f"/session/{session_id}", timeout=10)
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def abort(self) -> bool:
        """Cancel the call in flight, if any. Safe from another thread (the UI thread, while a
        turn blocks in a worker): it sets the cancel flag — so the call stops retrying and
        discards any partial reply — and interrupts the session so the model actually stops.
        Returns True if there was a live call to abort."""
        sid = self._inflight_sid
        self._cancel.set()
        if not sid:
            return False
        self._interrupt(sid)
        return True

    def revert_to_recent_user(self, session_id: str, back: int = 1) -> bool:
        """Revert `session_id` to the `back`-th most recent *user* message — dropping it and
        everything after it (e.g. a just-aborted reply), so a cancelled-then-retyped turn
        continues from clean context. Best-effort: any error (or too few user messages) leaves
        the session as-is."""
        try:
            page = self._request("GET", f"/session/{session_id}/message?order=desc&limit=100",
                                 timeout=10) or {}
        except (urllib.error.URLError, OSError, ValueError):
            return False
        users = [m["id"] for m in page.get("data") or [] if m.get("type") == "user" and m.get("id")]
        if len(users) < back:
            return False
        return self._revert_to(session_id, users[back - 1])

    def _revert_to(self, session_id: str, message_id: str) -> bool:
        """Drop `message_id` and everything after it. Campaign files are left alone — what an
        abandoned turn wrote is the orchestrator's to roll back, not opencode's."""
        try:
            self._request("POST", f"/session/{session_id}/revert/stage",
                          {"messageID": message_id, "files": False}, timeout=10)
            self._request("POST", f"/session/{session_id}/revert/commit", timeout=10)
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def prompt(self, session_id: str, agent: str, text: str, whole: bool = False) -> str:
        """Prompt `agent` on `session_id`; return its text.

        `whole=True` joins every text block of the turn (for replies whose content spans
        blocks, e.g. a checker that writes findings and then calls `report_findings`);
        otherwise the last block (the runner's narration)."""
        return self._exchange(session_id, agent, text, whole).text

    def prompt_full(self, session_id: str, agent: str, text: str, whole: bool = False) -> Reply:
        """Prompt `agent`; return a `Reply` (text + the tools called this turn + their inputs)."""
        return self._exchange(session_id, agent, text, whole)

    def ensure_tool(self, session_id: str, agent: str, reply: Reply, *, tool: str,
                    nudge: str, args: tuple[str, ...] = (), tries: int = 1,
                    whole: bool = False) -> Reply:
        """Safety hatch for tool-call-delimited tasks (task_complete, report_findings): make
        sure `reply` carries a call to `tool` with every arg in `args` non-empty. If it doesn't,
        send `nudge` as a follow-up prompt and re-read, up to `tries` times; return the final
        Reply. A no-op (no extra model call) when the tool was already called correctly."""
        def satisfied(r: Reply) -> bool:
            if tool not in r.tools:
                return False
            inp = r.tool_inputs.get(tool) or {}
            return all(str(inp.get(a, "")).strip() for a in args)

        for _ in range(tries):
            if satisfied(reply):
                break
            reply = self.prompt_full(session_id, agent, nudge, whole=whole)
        return reply

    def _model_limit(self, provider_id: str, model_id: str) -> dict | None:
        """A model's `limit` (`context`, `output`, optionally `input`) from the server's model
        catalog — fetched once and cached for the server's lifetime."""
        if self._models is None:
            try:
                self._models = (self._request("GET", "/model", timeout=15) or {}).get("data") or []
            except (urllib.error.URLError, OSError, ValueError):
                self._models = []
        for m in self._models:
            if m.get("providerID") == provider_id and m.get("id") == model_id:
                return m.get("limit")
        return None

    def context_usage(self, session_id: str) -> ContextUsage | None:
        """`session_id`'s live context footprint: the tokens its most recent model call sent
        (the whole context goes out on every call, so this is the current size) against the
        model's input ceiling. Best-effort — None on any lookup miss."""
        try:
            page = self._request("GET", f"/session/{session_id}/message?order=desc&limit=50",
                                 timeout=15) or {}
        except (urllib.error.URLError, OSError, ValueError):
            return None
        last = next((m for m in page.get("data") or []
                     if m.get("type") == "assistant" and m.get("tokens")), None)
        if last is None:
            return None
        tok = last["tokens"]
        cache = tok.get("cache") or {}
        used = ((tok.get("input") or 0) + (tok.get("output") or 0)
                + (cache.get("read") or 0) + (cache.get("write") or 0))
        model = last.get("model") or {}
        limit = self._model_limit(model.get("providerID"), model.get("id"))
        if not (used and limit and limit.get("context")):
            return None
        return ContextUsage(tokens=used, context_limit=limit.get("input") or limit["context"])


def read_turn(msgs: list[dict]) -> tuple[list[str], list[tuple[str, dict]], str | None]:
    """A turn's messages → (text blocks, (tool name, input) calls, error or None), in order.
    The error is the turn's failure as opencode reported it — a failed or interrupted idle, or
    an assistant message carrying an error."""
    texts: list[str] = []
    calls: list[tuple[str, dict]] = []
    error = None
    for m in msgs:
        kind = m.get("type")
        if kind == "assistant":
            for c in m.get("content") or []:
                if c.get("type") == "text" and c.get("text"):
                    texts.append(c["text"])
                elif c.get("type") == "tool" and c.get("name"):
                    calls.append((c["name"], (c.get("state") or {}).get("input") or {}))
            if m.get("error"):
                error = _error_text(m["error"])
        elif kind == "idle" and m.get("outcome") != "succeeded":
            error = _error_text(m.get("error")) if m.get("error") else f"turn {m.get('outcome')}"
    return texts, calls, error


def _error_text(err) -> str:
    if isinstance(err, dict):
        return str(err.get("message") or err.get("type") or err.get("_tag") or err)[:200]
    return str(err)[:200]


def pick_text(texts: list[str], whole: bool) -> str:
    """`whole=True` → every text block joined; otherwise the last one."""
    kept = [t.strip() for t in texts if t.strip()]
    if not kept:
        return ""
    return "\n".join(kept) if whole else kept[-1]
