"""
The canon lint — the deterministic half of keeping the campaign consistent.

It checks what code can check, so no model has to audit it: every registry file's frontmatter is
there and filled (identity, status, summary, the type's vitals), NPCs carry their capability
sections, stateful entities have a stamped state file, every `[[link]]` resolves, slugs are unique,
secrets carry ids, and every reveal the knowledge ledger records names a real secret. Whether the
committed values *cohere* is the narrative-checker's job, not this one.

Run it between sessions, after an authoring dispatch: `lint_campaign` returns the issues, and
`brief` formats them as the one correction the dispatching code sends back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .registry import (FrontmatterError, TYPE_DIRS, as_text, dashboard_slugs, entity_files,
                       read_frontmatter, scan, split_frontmatter)
from .reveals import HIDDEN, LEARNED, REVEALED, campaign_files

# Every registry file's frontmatter carries these.
COMMON = ["slug", "name", "type", "status", "summary"]

# Each type's vitals — committed at authoring time, never a punt. The templates in
# skills/canon-conventions/templates carry the same keys; keep them in step.
VITALS: dict[str, list[str]] = {
    "npc": ["full-name", "race", "pronouns", "age", "role", "affiliation"],
    "faction": ["kind", "scale", "seat", "leadership", "founded"],
    "location": ["kind", "region", "setting", "controlled-by", "scale"],
    "region": ["kind", "terrain", "seat-of-power", "population"],
    "item": ["kind", "rarity", "form", "origin"],
    "concept": ["kind"],
    "creature": [],
    "pc": ["race", "class", "level", "ability-scores", "pronouns"],
    "arc": ["tier"],
}

# Body sections that must exist and carry content. An NPC has none: its file starts as a shim
# and grows sections as it gains weight (design/luna.md § Campaign layout).
SECTIONS: dict[str, list[str]] = {
    "creature": ["Stat block"],
}

# Types whose `<slug>.state.md` must exist (a location, region, item or concept has one only when
# it has live state).
STATEFUL = {"pc", "npc", "faction", "arc"}

STATUSES = {"active", "dormant", "hidden", "dead", "destroyed", "resolved", "named-only"}

_PUNT = {"tbd", "todo", "to do", "dm decides", "as needed", "unknown", "?", "??", "???",
         "n/a", "na", "—", "-", "...", "none yet"}
_LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_OLD_FLAG = re.compile(r"\[hidden\]|\[revealed:\s*S\d+\]")
_AS_OF = re.compile(r"^S\d+$")


@dataclass
class Issue:
    rel: str        # path relative to campaign/
    message: str

    def __str__(self) -> str:
        return f"- {self.rel}: {self.message}"


def lint_campaign(root: Path | str) -> list[Issue]:
    """Every issue in the campaign under `root` (a project dir holding `campaign/`)."""
    campaign = Path(root) / "campaign"
    if not campaign.is_dir():
        return []
    issues: list[Issue] = []
    issues += _lint_entities(campaign)
    issues += _lint_links(campaign)
    issues += _lint_secrets(campaign)
    return issues


def unfilled(value) -> bool:
    v = as_text(value)
    if not v:
        return True
    if "<" in v and ">" in v:
        return True
    return v.lower().strip(" .") in _PUNT


def _lint_entities(campaign: Path) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[str, str] = {}
    for f in entity_files(campaign):
        rel = f.relative_to(campaign).as_posix()
        try:
            fm, body = split_frontmatter(f.read_text(encoding="utf-8"))
        except FrontmatterError as e:
            issues.append(Issue(rel, str(e)))
            continue
        except OSError:
            continue
        if fm is None:
            issues.append(Issue(rel, "no frontmatter block at the top of the file"))
            continue
        etype = as_text(fm.get("type")).lower()
        missing = [k for k in COMMON if unfilled(fm.get(k))]
        if etype in VITALS:
            missing += [k for k in VITALS[etype] if unfilled(fm.get(k))]
        if missing:
            issues.append(Issue(rel, "frontmatter missing or unfilled: " + ", ".join(missing)))
        slug = as_text(fm.get("slug"))
        if slug and slug != f.stem:
            issues.append(Issue(rel, f"slug `{slug}` does not match the file name `{f.stem}`"))
        expected_dir = TYPE_DIRS.get(etype)
        if etype and expected_dir is None:
            issues.append(Issue(rel, f"unknown type `{etype}`"))
        elif expected_dir and f.parent != campaign / expected_dir:
            issues.append(Issue(rel, f"type `{etype}` belongs in {expected_dir}/"))
        status = as_text(fm.get("status"))
        if status == "named-only":
            issues.append(Issue(rel, "still a named-only stub — author the full file"))
        elif status and status not in STATUSES:
            issues.append(Issue(rel, f"status `{status}` is not one of {', '.join(sorted(STATUSES))}"))
        if etype == "arc" and as_text(fm.get("tier")) not in ("major", "minor", ""):
            issues.append(Issue(rel, "tier must be `major` or `minor`"))
        for sec in SECTIONS.get(etype, []):
            if not _section_filled(body, sec):
                issues.append(Issue(rel, f"missing or empty `## {sec}` section"))
        if etype in STATEFUL and status != "named-only":
            issues += _lint_state(campaign, f)
        if slug:
            if slug in seen:
                issues.append(Issue(rel, f"slug `{slug}` is already used by {seen[slug]}"))
            else:
                seen[slug] = rel
    return issues


def _lint_state(campaign: Path, info: Path) -> list[Issue]:
    state = info.with_name(info.name[:-3] + ".state.md")
    rel = state.relative_to(campaign).as_posix()
    if not state.is_file():
        return [Issue(info.relative_to(campaign).as_posix(), f"missing its state file {rel}")]
    try:
        fm, _ = split_frontmatter(state.read_text(encoding="utf-8"))
    except (OSError, FrontmatterError) as e:
        return [Issue(rel, str(e))]
    as_of = as_text((fm or {}).get("as-of"))
    if not _AS_OF.match(as_of):
        return [Issue(rel, "frontmatter needs `as-of: S<n>`")]
    return []


def _section_filled(body: str, name: str) -> bool:
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and m.group(1).strip().lower().startswith(name.lower()):
            start = i + 1
            break
    if start is None:
        return False
    for line in lines[start:]:
        if _HEADING.match(line):
            break
        t = re.sub(r"^[-*]\s*|\*\*[^*]+:\*\*\s*", "", _COMMENT.sub("", line).strip()).strip()
        if t and not re.fullmatch(r"<[^>]*>", t):
            return True
    return False


def _lint_links(campaign: Path) -> list[Issue]:
    known = {e.slug for e in scan(campaign)} | dashboard_slugs(campaign)
    issues: list[Issue] = []
    for path in campaign_files(campaign):
        try:
            text = _COMMENT.sub("", path.read_text(encoding="utf-8"))
        except OSError:
            continue
        bad = sorted({m.group(1).strip() for m in _LINK.finditer(text)} - known)
        if bad:
            issues.append(Issue(path.relative_to(campaign).as_posix(),
                                "links resolve to nothing: " + ", ".join(f"[[{b}]]" for b in bad)))
    return issues


def _lint_secrets(campaign: Path) -> list[Issue]:
    issues: list[Issue] = []
    homes: dict[str, str] = {}
    for path in campaign_files(campaign):
        rel = path.relative_to(campaign).as_posix()
        try:
            text = _COMMENT.sub("", path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if rel.endswith(".knowledge.md"):
            continue
        if _OLD_FLAG.search(text):
            issues.append(Issue(rel, "a secret flag has no id — write `[hidden:<id>]`"))
        for m in list(HIDDEN.finditer(text)) + list(REVEALED.finditer(text)):
            sid = m.group(1)
            if sid in homes and homes[sid] != rel:
                issues.append(Issue(rel, f"secret id `{sid}` is also used in {homes[sid]}"))
            homes.setdefault(sid, rel)
    for led in sorted((campaign / "characters").glob("*.knowledge.md")):
        rel = led.relative_to(campaign).as_posix()
        try:
            text = led.read_text(encoding="utf-8")
        except OSError:
            continue
        bad = sorted({m.group(1) for m in LEARNED.finditer(text)} - homes.keys())
        if bad:
            issues.append(Issue(rel, "records learning secrets that don't exist: " + ", ".join(bad)))
    return issues


def arcs_not_stamped(root: Path | str, n: int) -> list[str]:
    """Arcs whose state file isn't stamped `as-of: S<n>` — the coverage check after an arc
    reconcile pass."""
    campaign = Path(root) / "campaign"
    out = []
    for e in scan(campaign):
        if e.type != "arc":
            continue
        state = e.path.with_name(e.path.name[:-3] + ".state.md")
        try:
            fm, _ = split_frontmatter(state.read_text(encoding="utf-8"))
        except (OSError, FrontmatterError):
            fm = None
        if as_text((fm or {}).get("as-of")) != f"S{n}":
            out.append(e.slug)
    return out


def world_missing(root: Path | str) -> list[str]:
    """The world stage's one disk deliverable: the player's primer."""
    if (Path(root) / "campaign" / "documents" / "primer.md").is_file():
        return []
    return ["`campaign/documents/primer.md`, the player's spoiler-free primer to the world."]


def setup_missing(root: Path | str) -> list[str]:
    """Setup deliverables, read from disk so a resume only authors unfinished work."""
    campaign = Path(root) / "campaign"
    entries = scan(campaign)
    arcs = [e for e in entries if e.type == "arc"]
    majors = [e for e in arcs if e.meta.get("tier") == "major"]
    minors = [e for e in arcs if e.meta.get("tier") == "minor"]
    missing = []
    if len(majors) != 1:
        missing.append(f"Exactly one major arc is required; found {len(majors)}.")
    if not minors:
        missing.append("At least one minor arc hooked into the major arc is required.")
    for arc in minors:
        if len(majors) == 1 and arc.meta.get("hooks-into") != majors[0].slug:
            missing.append(f"arcs/{arc.slug}.md needs `hooks-into: {majors[0].slug}`.")
    states = {e.path.with_name(e.path.stem + ".state.md") for e in entries if e.type in STATEFUL}
    states.update(campaign.glob("**/*.state.md"))
    states.update(campaign / "state" / f"{name}.md"
                  for name in ("current", "calendar", "threads", "clocks"))
    for path in sorted(states):
        if as_text((read_frontmatter(path) or {}).get("as-of")) != "S0":
            missing.append(f"{path.relative_to(campaign).as_posix()} needs initial state stamped `as-of: S0`.")
    return missing


def brief(issues: list[Issue]) -> str:
    """The issue list as the body of a correction message."""
    return "\n".join(str(i) for i in issues)
