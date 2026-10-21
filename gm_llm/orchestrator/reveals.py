"""
One write per reveal (design/luna.md § Campaign layout).

A secret is tagged where it lives — `[hidden:<id>]`, with a `Known to:` line under it. When the PC
learns it, the knowledge ledger records that once, by id: `[learned:<id> S<n>]`. `sync_reveals`
then does the mirror half in code: the home file's tag becomes `[revealed:<id> S<n>]` and the PC
joins its `Known to:` line. The model never keeps the two layers in step by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

HIDDEN = re.compile(r"\[hidden:([a-z0-9][a-z0-9-]*)\]")
REVEALED = re.compile(r"\[revealed:([a-z0-9][a-z0-9-]*)\s+S(\d+)\]")
LEARNED = re.compile(r"\[learned:([a-z0-9][a-z0-9-]*)\s+S(\d+)\]")
_KNOWN_TO = re.compile(r"^(.*?Known to:\s*)(.*)$")
_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(?!Known to:)")


def campaign_files(campaign: Path) -> list[Path]:
    """Every markdown file under campaign/ except session records (transcripts and digests
    quote play; they are not where secrets live)."""
    campaign = Path(campaign)
    return [p for p in sorted(campaign.rglob("*.md"))
            if "sessions" not in p.relative_to(campaign).parts and p.name != "INDEX.md"]


def learned(campaign: Path) -> dict[str, tuple[int, str]]:
    """id → (session, pc slug) for every `[learned:…]` in a knowledge ledger. The earliest
    session wins if a ledger names an id twice."""
    out: dict[str, tuple[int, str]] = {}
    for led in sorted((Path(campaign) / "characters").glob("*.knowledge.md")):
        pc = led.name[: -len(".knowledge.md")]
        try:
            text = led.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in LEARNED.finditer(text):
            sid, n = m.group(1), int(m.group(2))
            if sid not in out or n < out[sid][0]:
                out[sid] = (n, pc)
    return out


def sync_reveals(campaign: Path) -> int:
    """Flip every learned secret's home tag to revealed and add the PC to its `Known to:`
    line. Idempotent. Returns how many tags it flipped."""
    campaign = Path(campaign)
    todo = learned(campaign)
    if not todo:
        return 0
    flipped = 0
    for path in campaign_files(campaign):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "[hidden:" not in text:
            continue
        lines = text.splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            for m in list(HIDDEN.finditer(line)):
                sid = m.group(1)
                if sid not in todo:
                    continue
                n, pc = todo[sid]
                line = line.replace(m.group(0), f"[revealed:{sid} S{n}]", 1)
                lines[i] = line
                flipped += 1
                changed = True
                _add_known_to(lines, i, pc)
        if changed:
            path.write_text("".join(lines), encoding="utf-8")
    return flipped


def _add_known_to(lines: list[str], i: int, pc: str) -> None:
    """Add `[[pc]]` to the end of the `Known to:` entry of the secret that starts on line i
    (the first one before the next list item or heading). The entry may wrap onto indented
    lines below it."""
    link = f"[[{pc}]]"
    for j in range(i, min(i + 16, len(lines))):
        if j > i and (_ITEM.match(lines[j]) or lines[j].lstrip().startswith("#")):
            return  # the secret's bullet ended without a Known to: line
        m = _KNOWN_TO.match(lines[j].rstrip("\n"))
        if not m:
            continue
        last = j
        while (last + 1 < len(lines) and lines[last + 1].startswith((" ", "\t"))
               and lines[last + 1].strip() and not _ITEM.match(lines[last + 1])):
            last += 1
        if any(link in lines[k] for k in range(j, last + 1)):
            return
        end = "\n" if lines[last].endswith("\n") else ""
        if last == j:
            rest = m.group(2).strip().rstrip(".;,")
            new = f"{rest}, {link}" if rest and rest not in ("—", "-", "nobody", "no one") else link
            lines[j] = f"{m.group(1)}{new}{end}"
        else:
            lines[last] = f"{lines[last].rstrip().rstrip('.;,')}, {link}{end}"
        return
