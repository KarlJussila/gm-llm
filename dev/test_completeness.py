#!/usr/bin/env python3
"""Standalone checks for orchestrator.completeness (no pytest; run me directly)."""
import sys
from pathlib import Path

OPENCODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(OPENCODE))

from orchestrator.completeness import lint_text, lint_file  # noqa: E402

NPC_FULL = """\
---
slug: x
name: X
type: npc
status: active
---
# X
## Vitals
- **Full name:** Lysa Fenn
- **Race / lineage:** human
- **Pronouns:** she/her
- **Age:** early 40s
- **Role / station:** harbormaster
- **Affiliation:** unaffiliated
## Stats (rough sketch)
- **Equivalent level:** ~3
- **Ability scores:** STR 9 · DEX 11 · CON 11 · INT 14 · WIS 15 · CHA 13
- **Proficiencies:** Insight, Deception
## Abilities
None.
## Identity
prose
"""

NPC_GAPS = """\
---
type: npc
---
# X
## Vitals
- **Full name:** Lysa Fenn
- **Race / lineage:** <human, dwarf, …>
- **Pronouns:** she/her
- **Age:** TBD
- **Role / station:** harbormaster
## Stats (rough sketch)
- **Equivalent level:** <gauge>
- **Ability scores:** <STR …>
## Abilities
None.
## Identity
"""

NPC_NO_VITALS = """\
---
type: npc
---
# X
## Identity
no vitals block at all
"""

FACTION_FULL = """\
---
type: faction
---
# F
## Vitals
- **Kind:** rebel cell
- **Scale:** a dozen
- **Seat:** [[saltgate]]
- **Leadership:** leaderless cells
- **Founded:** two years ago
"""

PC_FILE = """\
---
type: pc
---
# Hero
"""


def check(text, *, etype, missing, ok, sections=(), label):
    r = lint_text(text)
    assert r.type == etype, f"{label}: type {r.type!r} != {etype!r}"
    assert sorted(r.missing) == sorted(missing), f"{label}: missing {r.missing} != {missing}"
    assert sorted(r.missing_sections) == sorted(sections), \
        f"{label}: missing_sections {r.missing_sections} != {list(sections)}"
    assert r.ok == ok, f"{label}: ok {r.ok} != {ok}"
    print(f"  ok  {label}")


check(NPC_FULL, etype="npc", missing=[], ok=True, label="complete NPC passes")
check(NPC_GAPS, etype="npc",
      missing=["Race / lineage", "Age", "Affiliation"], sections=["Stats"], ok=False,
      label="placeholder/punt/absent fields + empty Stats section all flagged")
check(NPC_NO_VITALS, etype="npc",
      missing=["Full name", "Race / lineage", "Pronouns", "Age",
               "Role / station", "Affiliation"],
      sections=["Stats", "Abilities"], ok=False,
      label="no Vitals -> all fields + both NPC sections missing")
check(FACTION_FULL, etype="faction", missing=[], ok=True,
      label="complete faction passes (no required sections)")
check(PC_FILE, etype="pc", missing=[], ok=True, label="pc type is skipped")

# the shipped worked example must satisfy its own contract
ex = lint_file(OPENCODE / "skills/canon-conventions/examples/lysa-fenn.md")
assert ex.ok and not ex.missing, f"worked example incomplete: {ex.missing}"
print("  ok  worked example lysa-fenn.md is complete")

print("\nALL COMPLETENESS CHECKS PASS")
