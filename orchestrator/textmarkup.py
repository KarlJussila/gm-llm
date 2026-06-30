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
