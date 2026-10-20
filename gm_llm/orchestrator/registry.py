"""
The campaign registry — every slug-addressed file, read from its frontmatter.

Layout v2 (design/luna.md § Campaign layout): each entity, PC sheet and arc carries its identity in
YAML frontmatter — `slug`, `name`, `type`, `status`, `summary`, plus its type's vitals. `INDEX.md`
is *generated* from that frontmatter by `write_index`; no model ever writes it. The canon lint
(`lint.py`), the preloader (`canon.py`) and the reveal sync (`reveals.py`) all read the campaign
through `scan`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Where each type lives, relative to campaign/.
TYPE_DIRS: dict[str, str] = {
    "pc": "characters",
    "npc": "world/npcs",
    "faction": "world/factions",
    "location": "world/locations",
    "region": "world/regions",
    "item": "world/items",
    "concept": "world/concepts",
    "creature": "world/bestiary",
    "arc": "arcs",
}

# INDEX section order and headings.
_SECTIONS = [("pc", "PC"), ("npc", "NPCs"), ("faction", "Factions"), ("location", "Locations"),
             ("region", "Regions"), ("item", "Items"), ("concept", "Concepts"),
             ("creature", "Bestiary"), ("arc", "Arcs")]

# Companion files that sit beside an info file and are not registry entries themselves.
COMPANION_SUFFIXES = (".state.md", ".knowledge.md", ".repertoire.md")

_FRONTMATTER = re.compile(r"\A(?:\s*<!--.*?-->)*\s*---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)


class FrontmatterError(ValueError):
    pass


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """(frontmatter dict, body). (None, text) when the file has no frontmatter block.
    Raises FrontmatterError when the block is there but isn't a YAML mapping. Leading HTML
    comments before the opening `---` are tolerated (templates carry guidance there)."""
    m = _FRONTMATTER.match(text)
    if not m:
        return None, text
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise FrontmatterError(f"frontmatter is not valid YAML: {str(e).splitlines()[0]}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a key: value mapping")
    return {str(k): v for k, v in data.items()}, text[m.end():]


def read_frontmatter(path: Path) -> dict | None:
    try:
        return split_frontmatter(path.read_text(encoding="utf-8"))[0]
    except (OSError, FrontmatterError):
        return None


def as_text(value) -> str:
    """A frontmatter scalar as display text ('' for missing/None; lists joined)."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(as_text(v) for v in value)
    return str(value).strip()


@dataclass
class Entry:
    slug: str
    name: str
    type: str
    status: str
    summary: str
    path: Path                      # absolute path of the info file
    rel: str                        # path relative to campaign/
    meta: dict = field(default_factory=dict)

    @property
    def state_rel(self) -> str | None:
        """The companion state file, relative to campaign/, if it exists on disk."""
        p = self.path.with_name(self.path.name[:-3] + ".state.md")
        return self.rel[:-3] + ".state.md" if p.is_file() else None


def entity_files(campaign: Path) -> list[Path]:
    """Every file that should be a registry entry: the .md files in the type directories,
    minus companions (state, knowledge ledger, repertoire)."""
    out: list[Path] = []
    for sub in dict.fromkeys(TYPE_DIRS.values()):
        d = campaign / sub
        if not d.is_dir():
            continue
        out += [f for f in sorted(d.glob("*.md")) if not f.name.endswith(COMPANION_SUFFIXES)]
    return out


def scan(campaign: Path) -> list[Entry]:
    """Every registry entry readable from frontmatter. Files with no usable frontmatter are
    skipped here — the lint is what reports them."""
    campaign = Path(campaign)
    entries: list[Entry] = []
    for f in entity_files(campaign):
        fm = read_frontmatter(f)
        if not fm:
            continue
        slug = as_text(fm.get("slug")) or f.stem
        entries.append(Entry(
            slug=slug, name=as_text(fm.get("name")) or slug, type=as_text(fm.get("type")).lower(),
            status=as_text(fm.get("status")), summary=as_text(fm.get("summary")),
            path=f, rel=f.relative_to(campaign).as_posix(), meta=fm))
    return entries


def render_index(entries: list[Entry]) -> str:
    lines = ["# INDEX — campaign registry", "",
             "Generated from each file's frontmatter. Don't edit it — edit the file, and this "
             "is rebuilt.", ""]
    for etype, heading in _SECTIONS:
        rows = sorted((e for e in entries if e.type == etype), key=lambda e: e.slug)
        if not rows:
            continue
        lines += [f"## {heading}", ""]
        if etype == "arc":
            lines += ["| slug | name | tier | status | file | summary |", "|---|---|---|---|---|---|"]
            lines += [f"| {e.slug} | {e.name} | {as_text(e.meta.get('tier'))} | {e.status} | "
                      f"{e.rel} | {_cell(e.summary)} |" for e in rows]
        else:
            lines += ["| slug | name | status | file | summary |", "|---|---|---|---|---|"]
            lines += [f"| {e.slug} | {e.name} | {e.status} | {e.rel} | {_cell(e.summary)} |"
                      for e in rows]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def write_index(campaign: Path) -> bool:
    """Regenerate campaign/INDEX.md. Returns True if its content changed."""
    campaign = Path(campaign)
    target = campaign / "INDEX.md"
    text = render_index(scan(campaign))
    try:
        if target.is_file() and target.read_text(encoding="utf-8") == text:
            return False
        target.write_text(text, encoding="utf-8")
    except (OSError, ValueError):
        return False
    return True


# -- threads and clocks --------------------------------------------------------

_DASH_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|")


def dashboard_slugs(campaign: Path) -> set[str]:
    """Slugs of the threads and clocks — the first cell of each table row in
    state/threads.md and state/clocks.md. `[[links]]` may point at these too."""
    out: set[str] = set()
    for name in ("threads.md", "clocks.md"):
        try:
            text = (Path(campaign) / "state" / name).read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            m = _DASH_ROW.match(line.strip())
            if m and m.group(1) != "slug":
                out.add(m.group(1))
    return out
