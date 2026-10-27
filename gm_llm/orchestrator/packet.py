"""The AI player's character packet, generated from the PC's own files (design/benchmark.md
§ The fixture): the sheet's player-facing sections, the PC's state and the knowledge ledger. The
benchmark's player has no file access, so this is everything it knows about its character; the
autonomous player keeps its own copy of the sheet.

The sheet also holds DM-side material — the story hooks, and connections the character may not
know about — so only the sections below are taken from it. Links become names, and the ledger's
reveal tags are dropped; a line still carrying a `[hidden:…]` tag is left out.
"""

from __future__ import annotations

import re
from pathlib import Path

from .registry import FrontmatterError, as_text, scan, split_frontmatter

_SHEET_SECTIONS = ("Known capabilities", "Appearance", "Personality", "Backstory")
_VITALS = ("race", "class", "subclass", "level", "ability-scores", "pronouns")

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_TAG = re.compile(r"\s*\[(?:learned|revealed):[^\]]*\]")


def character_packet(campaign: Path | str) -> str:
    """The packet for the campaign's PC, or '' when there is no PC sheet to build it from."""
    return "\n\n".join(p for p in (character_sheet(campaign), character_situation(campaign)) if p)


def character_sheet(campaign: Path | str) -> str:
    """The packet's sheet: the PC's vitals and the sheet's player-facing sections."""
    pc, clean = _pc(campaign)
    if pc is None:
        return ""
    vitals = "\n".join(f"- {key}: {as_text(pc.meta[key])}" for key in _VITALS
                       if as_text(pc.meta.get(key)))
    parts = [f"# You are {pc.name}", vitals]
    parts += [f"## {title}\n\n{clean(body)}" for title, body in _sections(pc.path)
              if title in _SHEET_SECTIONS and clean(body)]
    return "\n\n".join(p for p in parts if p)


def character_situation(campaign: Path | str) -> str:
    """The packet's situation: where the PC stands and what they know."""
    pc, clean = _pc(campaign)
    if pc is None:
        return ""
    parts = []
    for suffix, title in ((".state.md", "Where you stand"), (".knowledge.md", "What you know")):
        body = clean(_body(pc.path.with_name(pc.slug + suffix)))
        if body:
            parts.append(f"## {title}\n\n{body.replace('## ', '### ')}")
    return "\n\n".join(parts)


def _pc(campaign: Path | str):
    """The PC's entry (None without one) and the cleaner for text the player may see."""
    entries = scan(Path(campaign))
    pc = next((e for e in entries if e.type == "pc"), None)
    names = {e.slug: e.name for e in entries}

    def clean(text: str) -> str:
        text = _COMMENT.sub("", text)
        text = _LINK.sub(lambda m: m.group(2) or names.get(m.group(1).strip(), m.group(1)), text)
        text = _TAG.sub("", text)
        return "\n".join(line for line in text.splitlines() if "[hidden:" not in line).strip()

    return pc, clean


def _body(path: Path) -> str:
    """A companion file's body, without its frontmatter or its own `# ` title."""
    try:
        _, body = split_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, FrontmatterError):
        return ""
    return re.sub(r"\A\s*# [^\n]*\n", "", body)


def _sections(path: Path) -> list[tuple[str, str]]:
    """The sheet's `## ` sections as (title, body) pairs."""
    out = []
    for chunk in re.split(r"^## ", _body(path), flags=re.M)[1:]:
        title, _, text = chunk.partition("\n")
        out.append((title.strip(), text))
    return out
