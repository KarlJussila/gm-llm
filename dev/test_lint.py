#!/usr/bin/env python3
"""Standalone checks for the campaign layout v2 code — the registry, the canon lint, the reveal
sync and session paths (no pytest; run me directly)."""
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.assets import opencode_assets_dir  # noqa: E402
from gm_llm.orchestrator import paths  # noqa: E402
from gm_llm.orchestrator.lint import arcs_not_stamped, lint_campaign  # noqa: E402
from gm_llm.orchestrator.phase import refresh_campaign  # noqa: E402
from gm_llm.orchestrator.registry import render_index, scan, split_frontmatter  # noqa: E402
from gm_llm.orchestrator.reveals import sync_reveals  # noqa: E402
from gm_llm.orchestrator.scaffold import scaffold_campaign  # noqa: E402

NPC = """\
---
slug: lysa-fenn
name: Lysa Fenn
type: npc
status: active
summary: the harbormaster
full-name: Lysa Fenn
race: human
pronouns: she/her
age: early 40s
role: harbormaster
affiliation: "[[harbor-cell]]"
---

# Lysa Fenn

## Stats (rough sketch)
- **Equivalent level:** ~3

## Abilities
None.

## Secrets
- [hidden:fenn-informant] Lysa feeds the patrol rotation to the
  [[harbor-cell]].
  Known to: [[lysa-fenn]]
"""

STATE = "---\nslug: {slug}\nlayer: state\nas-of: S{n}\n---\n\nNow.\n"

FACTION = """\
---
slug: harbor-cell
name: The Harbor Cell
type: faction
status: active
summary: the rebels
kind: rebel cell
scale: a dozen
seat: the docks
leadership: a council
founded: two years ago
---

# The Harbor Cell
"""

PC = """\
---
slug: bram
name: Bram
type: pc
status: active
summary: a dockhand
race: human
class: rogue
level: 2
ability-scores: STR 10 · DEX 16 · CON 12 · INT 10 · WIS 12 · CHA 14
pronouns: he/him
---

# Bram
"""

ARC = """\
---
slug: the-tide
name: The Tide
type: arc
status: active
summary: the uprising
tier: major
---

# The Tide
"""


def build(root: Path) -> Path:
    c = root / "campaign"
    files = {
        "world/npcs/lysa-fenn.md": NPC,
        "world/npcs/lysa-fenn.state.md": STATE.format(slug="lysa-fenn", n=2),
        "world/factions/harbor-cell.md": FACTION,
        "world/factions/harbor-cell.state.md": STATE.format(slug="harbor-cell", n=2),
        "characters/bram.md": PC,
        "characters/bram.state.md": STATE.format(slug="bram", n=2),
        "characters/bram.knowledge.md": "---\nslug: bram\nlayer: knowledge\nas-of: S2\n---\n\n## Knows\n- Docks.\n",
        "arcs/the-tide.md": ARC,
        "arcs/the-tide.state.md": STATE.format(slug="the-tide", n=2),
        "sessions/2/plan.md": "# plan\n",
        "sessions/1/plan.md": "# plan\n",
        "sessions/1/transcript.md": "## DM\n[[nobody-at-all]] is fine in a transcript.\n",
    }
    for rel, text in files.items():
        p = c / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return c


def issues(root):
    return [str(i) for i in lint_campaign(root)]


def run(label, fn):
    tmp = Path(tempfile.mkdtemp(prefix="gm-lint-"))
    try:
        fn(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"  ok  {label}")


def t_clean(tmp):
    build(tmp)
    assert issues(tmp) == [], issues(tmp)


def t_missing_vitals(tmp):
    c = build(tmp)
    p = c / "world/npcs/lysa-fenn.md"
    p.write_text(p.read_text().replace("age: early 40s\n", "age: TBD\n").replace("race: human\n", ""))
    out = issues(tmp)
    assert any("lysa-fenn.md" in i and "race" in i and "age" in i for i in out), out


def t_sections_and_slug(tmp):
    c = build(tmp)
    p = c / "world/npcs/lysa-fenn.md"
    # an NPC shim: no stats or abilities is fine
    p.write_text(p.read_text().replace("## Abilities\nNone.\n", "")
                 .replace("slug: lysa-fenn\nname", "slug: lysa\nname"))
    (c / "world/bestiary").mkdir(parents=True, exist_ok=True)
    (c / "world/bestiary/wolf.md").write_text(
        "---\nslug: wolf\nname: Wolf\ntype: creature\nstatus: active\nsummary: a wolf\n---\n"
        "\n# Wolf\n\n## Stat block\n<none yet>\n")
    out = issues(tmp)
    assert not any("lysa" in i and "`## Abilities`" in i for i in out), out
    assert any("wolf.md" in i and "`## Stat block`" in i for i in out), out
    assert any("does not match the file name" in i for i in out), out


def t_state_files(tmp):
    c = build(tmp)
    (c / "world/factions/harbor-cell.state.md").unlink()
    (c / "arcs/the-tide.state.md").write_text("---\nslug: the-tide\nlayer: state\n---\n")
    out = issues(tmp)
    assert any("missing its state file" in i for i in out), out
    assert any("as-of: S<n>" in i for i in out), out


def t_named_only_and_links(tmp):
    c = build(tmp)
    (c / "world/npcs/maret.md").write_text(
        "---\nslug: maret\nname: Maret\ntype: npc\nstatus: named-only\nsummary: a tavern keeper\n---\n")
    p = c / "arcs/the-tide.md"
    p.write_text(p.read_text() + "\nSee [[maret]], [[ghost-town]] and [[the-uprising-clock]].\n"
                 "<!-- [[in-a-comment]] is ignored -->\n")
    (c / "state").mkdir()
    (c / "state/clocks.md").write_text("| slug | clock |\n|---|---|\n| the-uprising-clock | 2/6 |\n")
    out = issues(tmp)
    assert any("named-only stub" in i for i in out), out
    bad = [i for i in out if "resolve to nothing" in i]
    assert len(bad) == 1 and "[[ghost-town]]" in bad[0] and "maret" not in bad[0] \
        and "clock" not in bad[0] and "comment" not in bad[0], bad


def t_secrets(tmp):
    c = build(tmp)
    (c / "world/factions/harbor-cell.md").write_text(
        FACTION + "\n- [hidden] untagged secret\n- [hidden:fenn-informant] a reused id\n")
    (c / "characters/bram.knowledge.md").write_text("- Knows a lie. [learned:no-such-secret S2]\n")
    out = issues(tmp)
    assert any("has no id" in i for i in out), out
    assert any("is also used in" in i for i in out), out
    assert any("no-such-secret" in i for i in out), out


def t_reveal_sync(tmp):
    c = build(tmp)
    (c / "characters/bram.knowledge.md").write_text(
        "## Knows\n- Lysa informs for the cell. [learned:fenn-informant S2]\n")
    assert sync_reveals(c) == 1
    text = (c / "world/npcs/lysa-fenn.md").read_text()
    assert "[revealed:fenn-informant S2]" in text and "[hidden:fenn-informant]" not in text
    assert "Known to: [[lysa-fenn]], [[bram]]" in text, text
    assert sync_reveals(c) == 0, "idempotent"
    assert issues(tmp) == [], issues(tmp)

    # A Known to: entry that wraps gets the PC at its end, not mid-sentence (luna6d S3).
    (c / "world/npcs/mira.md").write_text(
        "- [hidden:mira-1] The mine sits on a node.\n"
        "  Known to: [[lysa-fenn]] (partial: knows energy is drained,\n"
        "  but not by whom); [[mira]] (does not know).\n"
        "- Another fact.\n")
    (c / "characters/bram.knowledge.md").write_text(
        "## Knows\n- Lysa informs. [learned:fenn-informant S2]\n- The node. [learned:mira-1 S3]\n")
    assert sync_reveals(c) == 1
    lines = (c / "world/npcs/mira.md").read_text().splitlines()
    assert lines[1] == "  Known to: [[lysa-fenn]] (partial: knows energy is drained,", lines
    assert lines[2] == "  but not by whom); [[mira]] (does not know), [[bram]]", lines


def t_index_and_paths(tmp):
    c = build(tmp)
    refresh_campaign(tmp)
    idx = (c / "INDEX.md").read_text()
    assert "| lysa-fenn | Lysa Fenn | active | world/npcs/lysa-fenn.md | the harbormaster |" in idx
    assert "| the-tide | The Tide | major | active | arcs/the-tide.md | the uprising |" in idx
    assert render_index(scan(c)) == idx
    assert paths.latest_session(c) == 2
    assert paths.transcript(c, 1).is_file()
    assert arcs_not_stamped(tmp, 2) == [] and arcs_not_stamped(tmp, 3) == ["the-tide"]


def t_scaffold(tmp):
    scaffold_campaign(tmp)
    assert issues(tmp) == [], issues(tmp)
    assert (tmp / "campaign/INDEX.md").is_file()


def t_example(tmp):
    """The shipped worked example satisfies its own contract."""
    ex = opencode_assets_dir() / "skills/canon-conventions/examples"
    c = tmp / "campaign" / "world" / "npcs"
    c.mkdir(parents=True)
    for f in ex.glob("lysa-fenn*.md"):
        shutil.copy(f, c / f.name)
    out = [i for i in issues(tmp) if "resolve to nothing" not in i]  # its links point off-example
    assert out == [], out


def t_templates_parse(tmp):
    """Every template's frontmatter is valid YAML (placeholders and all)."""
    for f in sorted((opencode_assets_dir() / "skills/canon-conventions/templates").glob("*.md")):
        if f.name == "stat-block.template.md":
            continue
        fm, _ = split_frontmatter(f.read_text(encoding="utf-8"))
        assert fm is not None, f.name


def t_fixture(tmp):
    """The bench fixture lints clean."""
    out = issues(REPO / "dev" / "fixtures" / "hollowfell")
    assert out == [], out


for label, fn in [
    ("a complete campaign lints clean", t_clean),
    ("missing and punted vitals are flagged", t_missing_vitals),
    ("a creature's empty stat block and slug/file mismatches are flagged; an NPC shim isn't", t_sections_and_slug),
    ("stateful entities need a stamped state file", t_state_files),
    ("named-only stubs and dangling links are flagged; dashboards and comments resolve", t_named_only_and_links),
    ("untagged, reused and unknown secret ids are flagged", t_secrets),
    ("a learned secret flips its home tag and Known to, idempotently", t_reveal_sync),
    ("INDEX is generated from frontmatter; session paths; arc coverage", t_index_and_paths),
    ("a fresh scaffold lints clean", t_scaffold),
    ("the worked example meets the contract", t_example),
    ("every template's frontmatter parses", t_templates_parse),
    ("the hollowfell fixture lints clean", t_fixture),
]:
    run(label, fn)

print("\nALL LINT CHECKS PASS")
