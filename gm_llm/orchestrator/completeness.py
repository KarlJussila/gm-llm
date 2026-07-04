"""
Entity-completeness lint — the deterministic half of the completeness contract.

An entity file can satisfy its template and still be missing the identity basics a
runner needs at the table (an NPC with no surname or race, a location with no region),
because those lived only in freeform prose. The fix is a required `## Vitals` block —
a fixed set of labelled fields per entity type — and this lint, which checks in *code*
that every required field is present and actually filled (not a left-in `<placeholder>`
or a punt word).

This is the cheap, deterministic guard. It complements — does not replace — the
narrative-checker, which judges whether the committed values *cohere* with the rest of
canon. Code catches "no surname"; the checker catches "surname contradicts the faction
file."

Used standalone (`cli.py lint`) and, from slice (ii), inside the reconcile/prep gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Required Vitals fields per entity type. The label is matched case-insensitively and
# must appear as a `- **Label:** value` line inside the file's `## Vitals` section.
# The prompt-side source of these sets is the templates in
# gm_llm/assets/opencode/skills/canon-conventions/templates/ (each template's
# `## Vitals` lines) — keep in sync.
REQUIRED_FIELDS: dict[str, list[str]] = {
    "npc": [
        "Full name", "Race / lineage", "Pronouns", "Age",
        "Role / station", "Affiliation",
    ],
    "faction": ["Kind", "Scale", "Seat", "Leadership", "Founded"],
    "location": ["Kind", "Region", "Setting", "Controlled by", "Scale"],
    "item": ["Kind", "Rarity", "Form", "Origin"],
    "region": ["Kind / scale", "Terrain", "Seat of power", "Population"],
    # A worldbuilding concept (cosmological force, cataclysm, magic system, phenomenon).
    # Just `Kind` — the body is free-form, so there are no required sections.
    "concept": ["Kind"],
    # The PC's mechanical identity. Subclass is deliberately absent — it's conditional
    # (class/level-dependent), recorded when it applies but not gated. The fuller
    # proficiency/spell/feat picture lives in `## Known capabilities`, which accretes
    # through play and is not linted.
    "pc": ["Race / lineage", "Class", "Level", "Ability scores", "Pronouns"],
}

# Required body sections per type — must exist AND carry real content (not just a
# left-in <placeholder>). NPCs carry a rough capability sketch + an abilities list;
# matched by heading prefix, so "## Stats (rough sketch)" satisfies "Stats".
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "npc": ["Stats", "Abilities"],
}

# Values that read as a non-answer — an unfilled field, even if a line exists for it.
# Deliberately tight: legitimate values like "unaffiliated", "unclaimed", "contested",
# "leaderless" must pass.
_PUNT = {
    "tbd", "todo", "to do", "dm decides", "as needed", "unknown",
    "?", "??", "???", "n/a", "na", "—", "-", "...",
}

_FIELD_RE = re.compile(r"^\s*[-*]\s*\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.*)$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(?P<title>.+?)\s*#*\s*$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class FileReport:
    path: Path
    type: str | None              # entity type from frontmatter, or None if unreadable
    missing: list[str] = field(default_factory=list)            # required Vitals fields with no filled value
    missing_sections: list[str] = field(default_factory=list)   # required sections absent or empty
    skipped: bool = False         # not a linted entity type (e.g. pc, world-truth doc)

    @property
    def ok(self) -> bool:
        return self.skipped or (
            self.type is not None and not self.missing and not self.missing_sections)


def _frontmatter_type(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        m = re.match(r"\s*type:\s*(\S+)", line)
        if m:
            return m.group(1).strip().lower()
    return None


def _section_body(text: str, name: str) -> str | None:
    """Return the body of the first section whose heading title starts with `name`
    (up to the next heading), or None if there's no such section."""
    name = _norm(name)
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m and _norm(m.group("title")).startswith(name):
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        if _HEADING_RE.match(line):
            break
        out.append(line)
    return "\n".join(out)


def _section_filled(text: str, name: str) -> bool:
    """True if the named section exists and carries at least one line of real content
    (not just comments and `<placeholder>` lines)."""
    body = _section_body(text, name)
    if body is None:
        return False
    body = _COMMENT_RE.sub("", body)
    for line in body.splitlines():
        t = line.strip()
        if not t:
            continue
        t = re.sub(r"^[-*]\s*", "", t)              # drop a list marker
        t = re.sub(r"^\*\*[^*]+:\*\*\s*", "", t)    # drop a bold label prefix
        t = t.strip()
        if not t or re.fullmatch(r"<[^>]*>", t):    # empty or a bare placeholder
            continue
        return True
    return False


def _filled_labels(section: str) -> set[str]:
    """Labels in the Vitals section that carry a real (non-punt, non-placeholder) value."""
    filled = set()
    for line in section.splitlines():
        m = _FIELD_RE.match(line)
        if not m:
            continue
        if _unfilled(m.group("value")):
            continue
        filled.add(_norm(m.group("label")))
    return filled


def _unfilled(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    if "<" in v and ">" in v:        # a left-in template <placeholder>
        return True
    return v.lower().strip(" .") in _PUNT


def _norm(label: str) -> str:
    # collapse whitespace and lowercase so "Race / lineage" matches regardless of spacing
    return re.sub(r"\s+", " ", label).strip().lower()


def lint_text(text: str, path: Path | str = "<string>") -> FileReport:
    path = Path(path)
    etype = _frontmatter_type(text)
    if etype not in REQUIRED_FIELDS:
        return FileReport(path, etype, skipped=True)
    vitals = _section_body(text, "Vitals")
    filled = _filled_labels(vitals) if vitals is not None else set()
    missing = [lbl for lbl in REQUIRED_FIELDS[etype] if _norm(lbl) not in filled]
    missing_sections = [s for s in REQUIRED_SECTIONS.get(etype, []) if not _section_filled(text, s)]
    return FileReport(path, etype, missing=missing, missing_sections=missing_sections)


def lint_file(path: Path | str) -> FileReport:
    path = Path(path)
    try:
        return lint_text(path.read_text(encoding="utf-8"), path)
    except OSError:
        return FileReport(path, None, skipped=True)


# Entity directories under campaign/world that can hold linted files.
_ENTITY_DIRS = ("npcs", "factions", "locations", "items", "regions", "concepts")


def lint_dir(root: Path | str) -> list[FileReport]:
    """Lint every entity info file under campaign/world and the PC sheet under
    campaign/characters (skipping `.state.md` / `.knowledge.md` companions)."""
    root = Path(root)
    campaign = root / "campaign"
    reports: list[FileReport] = []
    for sub in _ENTITY_DIRS:
        d = campaign / "world" / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.endswith(".state.md"):
                continue
            r = lint_file(f)
            if not r.skipped:
                reports.append(r)
    # The PC sheet lives in characters/ (its .state.md / .knowledge.md companions skip).
    chars = campaign / "characters"
    if chars.is_dir():
        for f in sorted(chars.glob("*.md")):
            if f.name.endswith((".state.md", ".knowledge.md")):
                continue
            r = lint_file(f)
            if not r.skipped:
                reports.append(r)
    return reports
