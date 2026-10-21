"""
Live event tap — stream the model's output to the terminal as it happens.

`Backend.prompt()` blocks until the turn is over and returns only its result, so a long
`dm` apply pass (or a checker) is a black box until it finishes. This subscribes to the
server's event stream in a background thread and prints assistant text as it streams,
plus a concise line per tool call — each labelled by which
session/agent is talking (`dm reconcile`, `check-propagation`, the
`log-extractor`…), so you can watch the dm and the checkers work and see exactly
where a pass goes wrong.

Opt-in (it's verbose) — the CLI wires it behind `--stream`. Read-only: it only
observes the event bus, never drives the run.
"""

from __future__ import annotations

import json
import re
import sys
import threading

from rich.markup import escape as _escape

from .textmarkup import inline as _inline


def _stdout_write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


class EventTap:
    def __init__(self, backend, write=None, markup: bool = False, on_tool=None):
        self.backend = backend
        # Where rendered lines go. Default: stdout (the CLI's --stream). A consumer
        # like the TUI passes its own writer to route the live log into a pane.
        self._write_cb = write or _stdout_write
        # Output dialect. A terminal sink gets ANSI; a Textual sink (markup=True) gets
        # console markup with body text escaped, so the pane is coloured the same way.
        self._markup = markup
        # Optional side-channel: called `on_tool(name, arg)` for each tool call, so a
        # consumer can surface a terse, spoiler-free activity signal separate from the
        # full stream (the TUI uses it for the setup-phase progress ticker).
        self._on_tool = on_tool
        self._stop = threading.Event()
        self._resp = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._titles: dict[str, str] = {}      # sessionID -> human title (lazy)
        self._tool_names: dict[str, str] = {}  # tool call id -> tool name
        self._cur: str | None = None           # session we're mid-line on
        self._cur_pid: str | None = None       # message part we're mid-stream on
        self._body = ""                        # markup mode: buffered partial line
        self._body_kind = "plain"              # kind of the buffered body text
        # ANSI only when we own a real terminal; a custom sink gets plain text.
        self._color = sys.stdout.isatty() and write is None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> "EventTap":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._flush_body()  # emit any trailing partial line
        try:
            if self._resp:
                self._resp.close()
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def log(self, text: str = "") -> None:
        """Print a full status line from the main thread without tearing a delta
        we're mid-stream on (closes the open line first)."""
        with self._lock:
            self._flush_body()
            if self._cur is not None:
                self._emit("\n")
                self._cur = None
            self._emit(text + "\n")

    def _emit(self, s: str) -> None:
        self._write_cb(s)

    # -- internals ----------------------------------------------------------

    _ANSI = {"heading": "1;36", "tool": "33", "reasoning": "2"}
    _TAGS = {"heading": "bold cyan", "tool": "yellow", "reasoning": "dim"}

    def _style(self, kind: str, s: str) -> str:
        """Render a chunk in the active dialect. `kind` is one of heading/tool/
        reasoning/plain. Markup mode escapes the body and wraps it in console tags;
        terminal mode wraps it in ANSI; otherwise it passes through plain."""
        if self._markup:
            s = _escape(s)
            tag = self._TAGS.get(kind)
            return f"[{tag}]{s}[/]" if tag else s
        if self._color:
            code = self._ANSI.get(kind)
            return f"\033[{code}m{s}\033[0m" if code else s
        return s

    # -- body text (markup mode buffers whole lines so Markdown renders) ----

    def _emit_body(self, kind: str, chunk: str) -> None:
        """Emit a delta of assistant/reasoning text. Terminal/plain mode streams the
        chunk as-is; markup mode buffers until a newline so `**bold**` and headings
        — which can be split across stream chunks — render per complete line."""
        if not self._markup:
            self._emit(self._style(kind, chunk))
            return
        if kind != self._body_kind:
            self._flush_body()
            self._body_kind = kind
        self._body += chunk
        while "\n" in self._body:
            line, self._body = self._body.split("\n", 1)
            self._emit(self._render_line(kind, line) + "\n")

    def _flush_body(self) -> None:
        """Emit any buffered partial line (on a section/tool break, or at stop)."""
        if self._body:
            self._emit(self._render_line(self._body_kind, self._body))
            self._body = ""

    def _render_line(self, kind: str, line: str) -> str:
        # Reasoning stays dim and literal; assistant prose gets Markdown bold, and a
        # leading `#`-heading becomes a bold line.
        if kind == "reasoning":
            return self._style("reasoning", line)
        m = re.match(r"\s*#{1,6}\s+(.*)", line)
        return f"[bold]{_inline(m.group(1))}[/bold]" if m else _inline(line)

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
        # HTTP fetch, and log() (called from the main thread) waits on this lock.
        title = self._title(sid)
        with self._lock:
            if sid != self._cur:
                self._flush_body()
                if self._cur is not None:
                    self._emit("\n")
                self._emit(self._style("heading", f"\n──── {title} ────\n"))
                self._cur = sid
                self._cur_pid = None
            elif block != self._cur_pid and self._cur_pid is not None:
                # A new block in the same session (a text block after a reasoning block, or a
                # reply resuming after a tool call). Close the previous block's line so
                # adjacent runs don't mash together ("…PC.Good…").
                self._flush_body()
                self._emit("\n")
            self._cur_pid = block
            self._emit_body("reasoning" if reasoning else "plain", chunk)

    def _emit_tool(self, sid: str | None, name: str, inp: dict) -> None:
        arg = self._tool_arg(inp)
        title = self._title(sid)  # HTTP on first lookup — keep it off the lock
        with self._lock:
            self._flush_body()
            if self._cur is not None:
                self._emit("\n")
                self._cur = None
            self._emit(self._style("tool", f"  ⚙ {title}: {name}{arg}\n"))
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
