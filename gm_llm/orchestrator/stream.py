"""
Live event tap — stream the model's output to the terminal as it happens.

`Backend.prompt()` blocks until the turn is over and returns only its result, so a long
`dm` apply pass (or a checker) is a black box until it finishes. This subscribes to the
server's event stream in a background thread and prints assistant text as it streams,
plus a concise line per tool call — each labelled by which
session/agent is talking (`dm reconcile`, `check-propagation`, the
`log-extractor`…), so you can watch the dm and the checkers work and see exactly
where a pass goes wrong.

Opt-in (it's verbose) — the CLI wires it behind `--stream`, and the engine routes it to
frontends as `stream` events. Read-only: it only observes the event bus, never drives the run.
"""

from __future__ import annotations

import json
import sys
import threading

class EventTap:
    """Subscribe to the server's event stream and hand each piece of live output to `sink`
    as `(kind, text)`: `heading` (a session starts talking), `text` (assistant prose),
    `reasoning`, or `tool` (one line per call). The text is laid out — newlines and
    separators included — but carries no styling; the sink decides how a kind looks. With no
    sink it prints to stdout, coloured when stdout is a terminal (the CLI's `--stream`)."""

    def __init__(self, backend, sink=None, on_tool=None):
        self.backend = backend
        self._sink = sink or self._print
        self._color = sink is None and sys.stdout.isatty()
        # Optional side-channel: called `on_tool(name, arg)` for each tool call, so a
        # consumer can surface a terse, spoiler-free activity signal separate from the
        # full stream (the engine uses it for setup's progress labels).
        self._on_tool = on_tool
        self._stop = threading.Event()
        self._resp = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._titles: dict[str, str] = {}      # sessionID -> human title (lazy)
        self._tool_names: dict[str, str] = {}  # tool call id -> tool name
        self._cur: str | None = None           # session we're mid-line on
        self._cur_pid: str | None = None       # message part we're mid-stream on

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> "EventTap":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._resp:
                self._resp.close()
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # -- output -------------------------------------------------------------

    _ANSI = {"heading": "1;36", "tool": "33", "reasoning": "2"}

    def _print(self, kind: str, s: str) -> None:
        code = self._ANSI.get(kind) if self._color else None
        sys.stdout.write(f"\033[{code}m{s}\033[0m" if code else s)
        sys.stdout.flush()

    def _emit(self, kind: str, s: str) -> None:
        self._sink(kind, s)

    def _title(self, sid: str | None) -> str:
        if not sid:
            return "?"
        if sid not in self._titles:
            self._titles[sid] = self.backend.session_title(sid) or sid[-6:]
        return self._titles[sid]

    def _run(self) -> None:
        try:
            self._resp = self.backend.open_events()  # streaming; closed by stop()
            for raw in self._resp:
                if self._stop.is_set():
                    break
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except ValueError:
                    continue
                self._handle(evt)
        except Exception:
            pass  # stream closed / server gone — nothing to do

    def _handle(self, evt: dict) -> None:
        kind, data = evt.get("type"), evt.get("data") or {}
        sid = data.get("sessionID")
        if kind in ("session.text.delta", "session.reasoning.delta"):
            # One block of text is a message id plus its ordinal within the message.
            block = f"{data.get('assistantMessageID')}:{kind}:{data.get('ordinal')}"
            self._emit_text(sid, block, data.get("delta") or "",
                            reasoning=kind == "session.reasoning.delta")
        elif kind == "session.tool.input.started":
            self._tool_names[data.get("id")] = data.get("name") or "tool"
        elif kind == "session.tool.called":
            self._emit_tool(sid, self._tool_names.get(data.get("id"), "tool"), data.get("input") or {})

    def _emit_text(self, sid: str | None, block: str, chunk: str, reasoning: bool) -> None:
        if not chunk:
            return
        # Resolve the session title before taking the lock — the first lookup is an
        # HTTP fetch, and the tool path waits on this lock.
        title = self._title(sid)
        with self._lock:
            if sid != self._cur:
                if self._cur is not None:
                    self._emit("text", "\n")
                self._emit("heading", f"\n──── {title} ────\n")
                self._cur = sid
                self._cur_pid = None
            elif block != self._cur_pid and self._cur_pid is not None:
                # A new block in the same session (a text block after a reasoning block, or a
                # reply resuming after a tool call). Close the previous block's line so
                # adjacent runs don't mash together ("…PC.Good…").
                self._emit("text", "\n")
            self._cur_pid = block
            self._emit("reasoning" if reasoning else "text", chunk)

    def _emit_tool(self, sid: str | None, name: str, inp: dict) -> None:
        arg = self._tool_arg(inp)
        title = self._title(sid)  # HTTP on first lookup — keep it off the lock
        with self._lock:
            if self._cur is not None:
                self._emit("text", "\n")
                self._cur = None
            self._emit("tool", f"  ⚙ {title}: {name}{arg}\n")
        if self._on_tool:
            self._on_tool(name, arg.strip())

    @staticmethod
    def _tool_arg(inp: dict) -> str:
        if not isinstance(inp, dict):
            return ""
        for k in ("filePath", "path", "pattern", "description", "command", "subagent_type", "title"):
            v = inp.get(k)
            if v:
                return "  " + str(v).splitlines()[0][:80]
        return ""
