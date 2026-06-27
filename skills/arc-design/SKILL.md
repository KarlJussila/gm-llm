---
name: arc-design
description: The craft of designing a new narrative arc for a D&D campaign — premise, stakes, key NPCs, turning points, tension curve, and engagement paths — with every load-bearing answer committed at design time. Covers WHAT makes a strong arc and the discipline of committing its answers; the file format is owned by the canon-conventions skill and the arc templates. Loaded by the dm to design a new arc. Adjusting an existing arc after play is a separate job, handled in the post-session arc pass.
---

# arc-design

## Player feedback — read first

Before designing, read `campaign/feedback/arc-design.md` if it exists. It holds accumulated,
player-specific guidance distilled from past sessions. Treat it as binding and let it override the
defaults here wherever they conflict.

This skill is for **designing a new arc**. Adjusting an arc after play (following divergence,
reconciling the arc to what was actually played) is a different disposition and a different job —
the post-session arc pass — so it is not here.

## Format is not your concern here — load canon-conventions + the arc templates

**Load `canon-conventions` and follow it for all format**, and build the arc from the
`arc-design` template (`arcs/{slug}.md`, the design file). The arc is a slug entity: register it
in `INDEX.md` (Arcs), link entities with `[[slug]]`, flag spoilers `[hidden]` + `Known to:`.

The arc is **two files**: the **design** (`{slug}.md`, what you write) and the **state**
(`{slug}.state.md`, a lightweight progress snapshot — written by the dm, not you). The design is a
**living document**: it is *not edited during play* (divergence is logged to the deltas log
instead), and it is **revised every session afterward** in the post-session arc pass, which assesses
what structural and detail changes each arc needs after play — redirecting, accelerating, merging,
deepening, recommitting answers — and reconciles the body toward what was actually played. Revise
the **body**, not just a status line. Status/progress stays out of the design and lives in the state
file, so the runner and the next plan get a quick at-a-glance read. You author the initial design.

## The rule that matters most: commit every answer

> **An arc commits its load-bearing answers at design time. Never "DM decides."**

This is the arc's whole job in the system: the dm (when planning) and the runner **pull answers
from the arc**. If the arc punts a fact downstream, a downstream agent fabricates one — and a
*different* one each time. So:

- **Every turning point commits its answer** — the reveal, the identity, the consequence. Write the
  real thing, flagged `[hidden]`.
- **Gather the load-bearing facts in the "committed answers" section** so they're trivial to pull.
  If the campaign will raise a question that matters to the plot, its answer is in the arc.
- **Never write "DM decides," "TBD," "as needed," or leave a load-bearing fact blank.** Decide it now.
- The **only** thing you leave open is the **player's path** — that's what the engagement paths are
  for. Fix the facts; leave the path free. (This is canon-conventions §1 at the arc layer.)

## What a strong arc has

Build the arc from the template's sections. What makes each good:

- **Premise & core conflict** — a real tension with tangible stakes. What concretely happens if it
  goes unresolved.
- **Stakes that are personal.** At campaign setup (or when a new PC joins), **make at least one
  major arc personal** — weave it into the character's backstory hooks and goals (a loss, a hunted
  past, a rival, a debt) so the central conflict matters to *this* character. Keep *how* the arc
  exploits their backstory spoiler-side.
- **Key NPCs & factions** — each with a committed identity and a want. The arc *owns* who these
  people really are; nothing downstream invents a parallel identity for an already-cast NPC.
- **Turning points (3–5)** — beats that shift direction or tension, each committing its answer.
- **Tension curve** — pace build-up → rising action → climax → falling action → resolution. Flat
  too long bores; spiking too often burns out.
- **Engagement paths** — direct / indirect / avoidance / alternative. This is the open part: how
  the player might come at it, including what happens if they ignore it (it escalates on its own).

## Craft principles

- **Every arc needs a hook** that draws the player in naturally — bond, curiosity, urgency, moral
  obligation. Never force engagement.
- **Flag the secrets and track who's in on them.** Turning points, the central truth, and villain
  motives are spoilers: `[hidden]` + `Known to:`. Cross-check the PC knowledge ledger
  (`characters/{slug}.knowledge.md`) so the arc starts from what the PC *actually* knows, and be
  explicit about known-vs-hidden when framing the hook.
- **Leave room for agency.** The plan is a direction, not a script — but "room for agency" means
  open *paths*, never undecided *facts*.
- **Arcs can run parallel or intersect.** Intersections force harder choices and richer moments;
  flag cross-arc dependencies so the dm can coordinate.

## Input to gather first
- `campaign/campaign.md` and `world/overview.md` — setting, tone, themes, central conflict.
- `world/` — the entities and factions the arc will use (and `INDEX.md` to reuse, not duplicate).
- `characters/{slug}.md` + `{slug}.knowledge.md` — the PC's backstory, goals, and what they know.
- Existing arcs (`arcs/`) — so a new arc complements rather than collides.

## When you're done
- The arc design reads as a committed story with every load-bearing answer fixed — no blanks.
- It's registered in `INDEX.md`, linked, and spoiler-flagged.
- Report the arc's intended **starting status** (usually `dormant`) so the dm can write the initial
  `{slug}.state.md` — you do not write arc state yourself.
