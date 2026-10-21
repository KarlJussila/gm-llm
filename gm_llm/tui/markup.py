"""Render a safe subset of inline Markdown as Textual console markup.

The play panes are `Static` widgets rendering console markup (not a Markdown
widget — we want selectable text and live streaming). Model output is Markdown,
so a bare ``**bold**`` would otherwise show its asterisks. This converts those
spans while escaping everything else first, so a stray ``[`` in the text can't
inject a tag.

Bold only, on purpose: ``*``/``_`` italics would false-match arithmetic, globs,
and ``snake_case`` identifiers that fill the behind-the-screen log.
"""

from __future__ import annotations

import re

from rich.markup import escape

# **bold** — must wrap non-space (real emphasis, not `a ** b`); non-greedy, spans
# newlines so a bold run split across a wrapped line still closes.
_BOLD = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*", re.S)


def inline(text: str) -> str:
    """Escape `text` for Textual markup, then render `**bold**` spans."""
    return _BOLD.sub(r"[bold]\1[/bold]", escape(text))


class StreamRenderer:
    """The engine's `stream` chunks → console markup for the behind-the-screen pane. Text is
    buffered to whole lines so a `**bold**` or a heading split across chunks still renders."""

    _TAGS = {"heading": "bold cyan", "tool": "yellow", "reasoning": "dim", "note": "dim"}

    def __init__(self):
        self._buf = ""
        self._kind = "text"

    def feed(self, kind: str, text: str) -> str:
        """Markup for every line `text` completes (possibly none)."""
        out = [self.flush()] if kind != self._kind else []
        self._kind = kind
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            out.append(self._line(line) + "\n")
        return "".join(out)

    def flush(self) -> str:
        line, self._buf = self._buf, ""
        return self._line(line) if line else ""

    def _line(self, line: str) -> str:
        if self._kind == "text":
            m = re.match(r"\s*#{1,6}\s+(.*)", line)
            return f"[bold]{inline(m.group(1))}[/bold]" if m else inline(line)
        tag = self._TAGS.get(self._kind)
        return f"[{tag}]{escape(line)}[/]" if tag else escape(line)
