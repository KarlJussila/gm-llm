"""
Live event tap — stream the model's output to the terminal as it happens.

`Backend.prompt()` is a blocking request that returns only the final text, so a long
`dm` apply pass (or a checker) is a black box until it finishes. This subscribes to
`opencode serve`'s `/event` SSE stream in a background thread and prints assistant
text as it streams, plus a concise line per tool call — each labelled by which
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
import urllib.parse
import urllib.request

from rich.markup import escape as _escape

from .textmarkup import inline as _inline


def _stdout_write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


class EventTap:
    def __init__(self, base: str, directory: str, write=None, markup: bool = False, on_tool=None):
        self.base = base
        self.directory = directory
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
        self._printed: dict[str, int] = {}     # partID -> chars already printed
        self._seen_tools: set[str] = set()     # tool partIDs already announced
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

    def _url(self, path: str) -> str:
        return f"{self.base}{path}?directory={urllib.parse.quote(self.directory)}"

    def _title(self, sid: str | None) -> str:
        if not sid:
            return "?"
        if sid not in self._titles:
            label = sid[-6:]
            try:
                req = urllib.request.Request(self._url(f"/session/{sid}"), method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    label = (json.loads(r.read().decode()).get("title") or label)
            except Exception:
                pass
            self._titles[sid] = label
        return self._titles[sid]

    def _run(self) -> None:
        try:
            req = urllib.request.Request(self._url("/event"), method="GET")
            self._resp = urllib.request.urlopen(req)  # streaming; closed by stop()
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
        if evt.get("type") != "message.part.updated":
            return
        part = (evt.get("properties") or {}).get("part") or {}
        kind = part.get("type")
        if kind == "text":
            self._emit_text(part.get("sessionID"), part.get("id"), part.get("text") or "", reasoning=False)
        elif kind == "reasoning":
            self._emit_text(part.get("sessionID"), part.get("id"), part.get("text") or "", reasoning=True)
        elif kind == "tool":
            self._emit_tool(part)

    def _emit_text(self, sid: str | None, pid: str | None, full: str, reasoning: bool) -> None:
        if not pid:
            return
        # Resolve the session title before taking the lock — the first lookup is an
        # HTTP fetch, and log() (called from the main thread) waits on this lock.
        title = self._title(sid)
        with self._lock:
            prev = self._printed.get(pid, 0)
            if len(full) <= prev:
                return
            chunk = full[prev:]
            self._printed[pid] = len(full)
            if sid != self._cur:
                self._flush_body()
                if self._cur is not None:
                    self._emit("\n")
                self._emit(self._style("heading", f"\n──── {title} ────\n"))
                self._cur = sid
                self._cur_pid = None
            elif pid != self._cur_pid and self._cur_pid is not None:
                # A new message part in the same session (e.g. a text part after a reasoning
                # part, or an assistant reply resuming after a tool call). Close the previous
                # part's line so adjacent runs don't mash together ("…PC.Good…").
                self._flush_body()
                self._emit("\n")
            self._cur_pid = pid
            self._emit_body("reasoning" if reasoning else "plain", chunk)

    def _emit_tool(self, part: dict) -> None:
        pid = part.get("id")
        if not pid or pid in self._seen_tools:
            return
        state = part.get("state") or {}
        if state.get("status") not in ("running", "completed"):
            return  # wait until the call actually fires
        self._seen_tools.add(pid)
        name = part.get("tool") or "tool"
        arg = self._tool_arg(state.get("input") or {})
        title = self._title(part.get("sessionID"))  # HTTP on first lookup — keep it off the lock
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
