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
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .logs import Logs, append


@dataclass(frozen=True)
class Reply:
    """A prompt's result: the agent's text, the set of tool names it called this
    response, and their input args. `tools` lets a caller detect an explicit signal
    the model raised via a tool (e.g. `task_complete`) without prose-parsing — see
    `prompt_full`. `tool_inputs` maps each tool name to its input dict (last call
    wins if called twice), so a caller can read structured fields — e.g. the
    `report_findings` tool's `verdict` and `report` fields."""
    text: str
    tools: frozenset[str] = field(default_factory=frozenset)
    tool_inputs: dict[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextUsage:
    """A session's live context footprint, read straight off opencode's own
    accounting. `threshold` mirrors opencode's auto-compaction trigger: it caps
    the model's output reservation at OUTPUT_TOKEN_MAX (32000) and auto-summarizes
    once cumulative tokens reach whatever's left of the window. With no input cap
    (this project's model) that leftover is `context - min(output, 32000)`; when
    the model advertises an input cap it's `input - min(20000, output, 32000)`
    instead. Nothing here is fetched from that trigger directly (opencode doesn't
    expose it) — this recomputes it from the same public numbers
    (`/config/providers`), so it can drift if opencode changes the formula, but
    it's the best available signal short of parsing their source."""
    tokens: int
    context_limit: int
    threshold: int

    @property
    def pct(self) -> float:
        return (self.tokens / self.threshold * 100) if self.threshold else 0.0


class BackendError(RuntimeError):
    pass


class BackendCancelled(BackendError):
    """The in-flight call was cancelled via `abort()` (e.g. the player hit the
    cancel key after a mistype). Raised instead of returning a partial/empty reply
    or retrying, so the turn unwinds cleanly before anything is committed."""
    pass


class Backend:
    def __init__(
        self,
        directory: str,
        port: int = 4181,
        turn_timeout: int = 360,
        retries: int = 6,
        min_call_gap: float = 1.0,
        logs: Logs | None = None,
    ):
        self.directory = str(Path(directory).resolve())
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        self.turn_timeout = turn_timeout
        self.retries = retries
        self.min_call_gap = min_call_gap
        self.logs = logs or Logs.under(project=self.directory)
        self._proc: subprocess.Popen | None = None
        self._owns_server = False
        self._last_call = 0.0
        # Cancellation: `abort()` (any thread) sets the event and aborts the session
        # whose id is parked in `_inflight_sid`; the running `prompt` loop sees the
        # event and raises BackendCancelled instead of retrying/returning.
        self._cancel = threading.Event()
        self._inflight_sid: str | None = None
        self.on_retry = None  # optional callback(agent, attempt, wait, reason)
        self._providers_cache: dict | None = None  # /config/providers, fetched once (static)

    # -- server lifecycle ---------------------------------------------------

    def start(self, ready_timeout: int = 60) -> "Backend":
        """Boot our own `opencode serve` and wait until it answers."""
        log = open(self.logs.serve, "w")
        exe = shutil.which("opencode") or "opencode"
        if os.name == "nt":
            # From `npm i -g opencode-ai`, `opencode` is an `opencode.cmd` shim that
            # CreateProcess can't launch directly, so run it through the shell (a bare
            # Popen list would fail with "not a valid Win32 application"). A new process
            # group isolates it from the TUI's console signals; stop() reaps the whole
            # tree with taskkill.
            self._proc = subprocess.Popen(
                f'"{exe}" serve --port {self.port}',
                cwd=self.directory, stdout=log, stderr=subprocess.STDOUT,
                shell=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            self._proc = subprocess.Popen(
                [exe, "serve", "--port", str(self.port)],
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
                if os.name == "nt":
                    # The server sits under a cmd.exe shim (.cmd); a graceful CTRL_BREAK
                    # risks cmd's "Terminate batch job (Y/N)?" prompt hanging shutdown, and
                    # kill() would reap only the shell. taskkill /T force-kills the whole
                    # tree (shell + opencode + its runtime children).
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
    def _text_parts(resp: dict) -> list[str]:
        parts = resp.get("parts", []) if isinstance(resp, dict) else []
        return [p.get("text", "") for p in parts if p.get("type") == "text" and p.get("text")]

    @classmethod
    def _last_text(cls, resp: dict) -> str:
        texts = cls._text_parts(resp)
        return texts[-1].strip() if texts else ""

    @classmethod
    def _all_text(cls, resp: dict) -> str:
        """Every text part joined — for replies whose content spans parts (e.g. a
        checker that runs a `todowrite` list, then submits its `report_findings`
        tool call: `_last_text` would keep only the last text part)."""
        return "\n".join(t.strip() for t in cls._text_parts(resp)).strip()

    def _recent_tool_names(self, session_id: str) -> frozenset[str]:
        """The names of every tool the agent called in the most recent turn — scanning
        every assistant message after the last user message in the session history.

        Must read history rather than the POST response: opencode splits a turn that calls
        a tool and then keeps producing output into multiple assistant messages, and the
        POST returns only the last, so a `task_complete` call the model follows with more
        text would be missed. Prompts are serialized (one in-flight), so the trailing
        assistant messages are exactly this turn's. Best-effort — any error yields empty."""
        return frozenset(name for name, _ in self._recent_tool_calls(session_id))

    def _recent_tool_calls(self, session_id: str) -> list[tuple[str, dict]]:
        """Every (tool_name, input_args) the agent called in the most recent turn —
        scanning every assistant message after the last user message. Pairs with
        `_recent_tool_names` (which derives just the names) and feeds `Reply.tool_inputs`
        via `prompt_full`. Best-effort — any error yields empty."""
        try:
            msgs = self._raw_get(f"/session/{session_id}/message", timeout=30)
        except (urllib.error.URLError, OSError, ValueError):
            return []
        if not isinstance(msgs, list):
            return []
        last_user = -1
        for i, m in enumerate(msgs):
            if isinstance(m, dict) and m.get("info", {}).get("role") == "user":
                last_user = i
        calls = []
        for m in msgs[last_user + 1:]:
            for p in (m.get("parts", []) if isinstance(m, dict) else []):
                if p.get("type") == "tool" and p.get("tool"):
                    state = p.get("state") or {}
                    calls.append((p["tool"], state.get("input") or {}))
        return calls

    def _dump_parts(self, session_id: str, agent: str, resp: dict, out: str) -> None:
        """Debug (logs.debug): append the reply's full part structure to the raw
        log, so we can see whether a checker's findings landed in an earlier part
        than its verdict (which `_last_text` would drop) vs. the model genuinely
        emitting only the verdict."""
        parts = resp.get("parts", []) if isinstance(resp, dict) else []
        types = [p.get("type") for p in parts]
        texts = [p.get("text", "") for p in parts if p.get("type") == "text" and p.get("text")]
        block = (f"\n{'=' * 72}\n{datetime.now(timezone.utc).isoformat(timespec='seconds')}  "
                 f"agent={agent}  session={session_id}\n"
                 f"part types ({len(parts)}): {types}\n"
                 f"text parts: {len(texts)}\n")
        for i, t in enumerate(texts):
            block += f"--- text part {i} ---\n{t}\n"
        block += f"--- _last_text returned (the checker's text output) ---\n{out}\n"
        append(self.logs.raw, block)

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

    def abort(self) -> bool:
        """Cancel the `prompt` call currently in flight, if any. Safe to call from
        another thread (the UI thread, while a turn blocks in a worker): it sets the
        cancel flag — so the prompt loop stops retrying, breaks its backoff, and
        discards any partial reply — and POSTs the server-side abort so the model
        actually stops generating. Returns True if there was a live call to abort."""
        sid = self._inflight_sid
        self._cancel.set()
        if not sid:
            return False
        try:
            self._raw_post(f"/session/{sid}/abort", {}, timeout=10)
        except (urllib.error.URLError, OSError, ValueError):
            pass  # best-effort: the cancel flag already frees the loop
        return True

    def revert_to_recent_user(self, session_id: str, back: int = 1) -> bool:
        """Revert `session_id` to the `back`-th most recent *user* message — dropping
        it and everything after it (e.g. a just-aborted assistant reply). `back=1` is
        the last user message (a cancel during the draft); `back=2` reaches past one
        intervening user message — a correction brief — to the player's own message,
        so cancelling mid-correction rolls back the whole turn, not just the
        correction. opencode finalizes the removal on the next prompt to this
        session, so a cancelled-then-retyped turn continues from clean context.
        Best-effort: any error (or too few user messages) leaves the session as-is."""
        try:
            msgs = self._raw_get(f"/session/{session_id}/message", timeout=10)
        except (urllib.error.URLError, OSError, ValueError):
            return False
        users = [
            m["info"]["id"]
            for m in (msgs if isinstance(msgs, list) else [])
            if isinstance(m, dict) and m.get("info", {}).get("role") == "user" and m["info"].get("id")
        ]
        if len(users) < back:
            return False
        target = users[-back]
        try:
            self._raw_post(f"/session/{session_id}/revert", {"messageID": target}, timeout=10)
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def prompt(self, session_id: str, agent: str, text: str, whole: bool = False) -> str:
        """Prompt `agent` on `session_id`; return its text."""
        return self._run_prompt(session_id, agent, text, whole=whole)

    def prompt_full(self, session_id: str, agent: str, text: str, whole: bool = False) -> Reply:
        """Prompt `agent`; return a `Reply` (text + tool names + tool inputs).

        Tool names and inputs come from the session history, NOT the POST response: when
        the model calls a tool and then keeps going (more reasoning, another tool, a
        closing line), opencode splits the turn into several assistant messages and the
        POST returns only the LAST one — so a `task_complete` call followed by any
        further output would be invisible in the response alone. We scan every assistant
        message since the last user message instead. `tool_inputs` maps each tool name to
        its input dict (last call wins), so a caller can read structured fields like the
        `report_findings` tool's `verdict` and `report`."""
        out = self._run_prompt(session_id, agent, text, whole=whole)
        calls = self._recent_tool_calls(session_id)
        names = frozenset(name for name, _ in calls)
        inputs: dict[str, dict] = {}
        for name, inp in calls:
            inputs[name] = inp  # last call wins (fine for signal tools called once)
        return Reply(out, names, inputs)

    def ensure_tool(self, session_id: str, agent: str, reply: Reply, *, tool: str,
                    nudge: str, args: tuple[str, ...] = (), tries: int = 1,
                    whole: bool = False) -> Reply:
        """Safety hatch for tool-call-delimited tasks (task_complete, report_findings):
        make sure `reply` carries a call to `tool` with every arg in `args` non-empty. If
        it doesn't, send `nudge` as a follow-up prompt and re-read, up to `tries` times;
        return the final Reply.

        The caller still handles a miss that survives every nudge (the true fallback) —
        this just makes that fallback the last resort instead of the first one, so a model
        that ended a turn without its terminal tool call gets told to make it rather than
        being silently second-guessed. A no-op (no extra model call) in the common case
        where the tool was already called correctly."""
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
        """A model's `limit` dict (`context`, `output`, optionally `input`) from
        `/config/providers` — fetched once and cached for the server's lifetime
        (static catalog data, not per-session state)."""
        if self._providers_cache is None:
            try:
                self._providers_cache = self._raw_get("/config/providers", timeout=15)
            except (urllib.error.URLError, OSError, ValueError):
                self._providers_cache = {}
        for p in (self._providers_cache.get("providers") or []):
            if p.get("id") == provider_id:
                return ((p.get("models") or {}).get(model_id) or {}).get("limit")
        return None

    def context_usage(self, session_id: str) -> ContextUsage | None:
        """`session_id`'s live context footprint: tokens actually sent on its
        most recent completed turn (that turn's `tokens.total` — the whole
        context goes out on every call, so this is the current size, not a
        delta) against the model's advertised limits. A dev/status-only signal
        — best-effort, returns None on any lookup miss (no history yet, an
        unrecognized model, a server hiccup); never worth failing a turn over."""
        try:
            msgs = self._raw_get(f"/session/{session_id}/message", timeout=15)
        except (urllib.error.URLError, OSError, ValueError):
            return None
        if not isinstance(msgs, list):
            return None
        info = None
        for m in reversed(msgs):
            i = m.get("info", {}) if isinstance(m, dict) else {}
            if i.get("role") == "assistant" and i.get("tokens"):
                info = i
                break
        if info is None:
            return None
        tok = info.get("tokens") or {}
        cache = tok.get("cache") or {}
        used = tok.get("total") or (
            (tok.get("input") or 0) + (tok.get("output") or 0)
            + (cache.get("read") or 0) + (cache.get("write") or 0))
        provider_id, model_id = info.get("providerID"), info.get("modelID")
        if not (used and provider_id and model_id):
            return None
        limit = self._model_limit(provider_id, model_id)
        if not limit or not limit.get("context"):
            return None
        # opencode caps the reply reservation at OUTPUT_TOKEN_MAX (32000), even for
        # models that advertise a larger `output` — mirror that so the threshold
        # matches for models with output > 32k, not just this project's mimo (32k).
        context = limit["context"]
        max_output = min(limit.get("output") or 32000, 32000)
        threshold = (max(0, limit["input"] - min(20000, max_output)) if limit.get("input")
                     else max(0, context - max_output))
        return ContextUsage(tokens=used, context_limit=context, threshold=threshold)

    def _run_prompt(self, session_id: str, agent: str, text: str, whole: bool = False) -> str:
        """Prompt `agent` on `session_id`; return its text. Retries on failure/empty/
        timeout with backoff, paced to ease rate limits.

        `whole=True` joins every text part (use for checkers, whose findings and verdict
        can land in separate parts); the default returns the last part (the runner's
        narration, a single clean block).

        Cancellable: `abort()` from another thread raises BackendCancelled here rather
        than retrying or returning a partial reply."""
        body = {"agent": agent, "parts": [{"type": "text", "text": text}]}
        self._cancel.clear()
        self._inflight_sid = session_id
        try:
            for attempt in range(self.retries):
                self._pace()
                try:
                    resp = self._raw_post(f"/session/{session_id}/message", body, self.turn_timeout)
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    out = self._all_text(resp) if whole else self._last_text(resp)
                    if self.logs.debug:
                        self._dump_parts(session_id, agent, resp, out)
                    if out:
                        return out
                    if self._recent_tool_names(session_id):
                        # A tool-call-only turn is a legitimate reply, not a failure —
                        # e.g. a checker told to submit report_findings and output
                        # nothing else. Retrying would re-send the same prompt (and
                        # re-fire the tool); the caller reads the call from history.
                        return ""
                    reason = "empty reply (likely a rate-limited/errored stream)"
                except BackendCancelled:
                    raise
                except urllib.error.HTTPError as e:
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    detail = e.read().decode(errors="replace")[:160] if hasattr(e, "read") else ""
                    reason = f"HTTP {e.code} {detail}"
                except (urllib.error.URLError, OSError, ValueError) as e:
                    if self._cancel.is_set():
                        raise BackendCancelled(f"{agent} call cancelled")
                    reason = str(e)
                wait = min(15 * (2 ** attempt), 120)
                if self.on_retry:
                    self.on_retry(agent, attempt + 1, wait, reason)
                if self._cancel.wait(wait):  # interruptible backoff — abort breaks the wait
                    raise BackendCancelled(f"{agent} call cancelled")
            raise BackendError(f"{agent} failed after {self.retries} retries")
        finally:
            self._inflight_sid = None
