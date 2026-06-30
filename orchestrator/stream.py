"""
Live event tap — stream the model's output to the terminal as it happens.

`Backend.prompt()` is a blocking request that returns only the final text, so a long
`dm` apply pass (or a checker) is a black box until it finishes. This subscribes to
`opencode serve`'s `/event` SSE stream in a background thread and prints assistant
text as it streams, plus a concise line per tool call — each labelled by which
session/agent is talking (`dm reconcile`, `check-propagation`, a delegated
`log-extractor`…), so you can watch the dm and the checkers work and see exactly
where a pass goes wrong.

Opt-in (it's verbose) — the CLI wires it behind `--stream`. Read-only: it only
observes the event bus, never drives the run.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.parse
import urllib.request


def _stdout_write(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


class EventTap:
    def __init__(self, base: str, directory: str, write=None):
        self.base = base
        self.directory = directory
        # Where rendered lines go. Default: stdout (the CLI's --stream). A consumer
        # like the TUI passes its own writer to route the live log into a pane.
        self._write_cb = write or _stdout_write
        self._stop = threading.Event()
        self._resp = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._titles: dict[str, str] = {}      # sessionID -> human title (lazy)
        self._printed: dict[str, int] = {}     # partID -> chars already printed
        self._seen_tools: set[str] = set()     # tool partIDs already announced
        self._cur: str | None = None           # session we're mid-line on
        # ANSI only when we own a real terminal; a custom sink gets plain text.
        self._color = sys.stdout.isatty() and write is None

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

    def log(self, text: str = "") -> None:
        """Print a full status line from the main thread without tearing a delta
        we're mid-stream on (closes the open line first)."""
        with self._lock:
            if self._cur is not None:
                self._emit("\n")
                self._cur = None
            self._emit(text + "\n")

    def _emit(self, s: str) -> None:
        self._write_cb(s)

    # -- internals ----------------------------------------------------------

    def _c(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self._color else s

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
        with self._lock:
            prev = self._printed.get(pid, 0)
            if len(full) <= prev:
                return
            chunk = full[prev:]
            self._printed[pid] = len(full)
            if sid != self._cur:
                if self._cur is not None:
                    self._emit("\n")
                self._emit(self._c("1;36", f"\n──── {self._title(sid)} ────\n"))
                self._cur = sid
            self._emit(self._c("2", chunk) if reasoning else chunk)

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
        with self._lock:
            if self._cur is not None:
                self._emit("\n")
                self._cur = None
            self._emit(self._c("33", f"  ⚙ {self._title(part.get('sessionID'))}: {name}{arg}\n"))

    @staticmethod
    def _tool_arg(inp: dict) -> str:
        if not isinstance(inp, dict):
            return ""
        for k in ("filePath", "path", "pattern", "description", "command", "subagent_type", "title"):
            v = inp.get(k)
            if v:
                return "  " + str(v).splitlines()[0][:80]
        return ""
