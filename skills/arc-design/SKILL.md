---
name: arc-design
description: The craft of designing a new narrative arc for a D&D campaign — premise, stakes, key NPCs, turning points, tension curve, and engagement paths — with every load-bearing answer committed at design time. Covers the major/minor arc model, WHAT makes a strong arc, and the discipline of committing its answers; the file format is owned by the canon-conventions skill and the arc templates. Loaded by the dm to design a new arc — the campaign's one major arc, or a minor arc hooked into it. Revising an existing arc after play is the apply-arcs pass, not this skill.
---

# arc-design

## Read first

Read `campaign/feedback/arc-design.md` if it exists — accumulated, player-specific guidance distilled
from past sessions. Treat it as binding; let it override the defaults here wherever they conflict.

## Build your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Gather context (see *Before you write*)
2. Design the arc: premise, stakes, key NPCs/factions, turning points, engagement paths
3. Lay out level pacing (major arc only — see *Level pacing*)
4. Author the arc file + `.state.md`; register in `INDEX.md` with `tier` and `hooks-into` (if minor)

## What you're designing

The campaign has **one major arc and several minor arcs that hook into it**. You're designing one:

- **The major arc** is the campaign's spine. Its central conflict is **personal** — built on this
  PC's backstory, goals, and bonds, so it matters to *this* character. `tier: major`.
- **A minor arc** is a focused subplot that **hooks into the major**: it earns its place by feeding
  it — escalating its clock, exposing one of its answers, or complicating its conflict. `tier: minor`,
  with `hooks-into:` set to the major and the cross-references wired **both ways**.

## The rule that matters most: commit every answer

> **An arc commits its load-bearing answers at design time. Never "DM decides."**

This is the arc's whole job in the system: the dm (when planning) and the runner (in play) **pull
answers from the arc**. If the arc punts a load-bearing fact downstream, a downstream agent
fabricates one — and a *different* one each time. So:

- **Every turning point commits its answer** — the reveal, the identity, the consequence. Write the
  real thing, flagged `[hidden]`.
- **Gather the load-bearing facts in the committed-answers section** so they're trivial to pull. If
  the campaign will raise a question that matters to the plot, its answer is in the arc.
- **Never write "DM decides," "TBD," "as needed," or leave a load-bearing fact blank.** Decide it now.
- The **only** thing you leave open is the **player's path** — that's what the engagement paths are
  for. Fix the facts; leave the path free.

## What a strong arc has

Build the arc from the template's sections. What makes each good:

- **Premise & core conflict** — a real tension with tangible stakes. What concretely happens if it
  goes unresolved.
- **Stakes that bite** — make the cost concrete and tie it to what the PC cares about. Keep *how* the
  arc exploits their backstory spoiler-side.
- **Key NPCs & factions** — each with a committed identity and a want. The arc *owns* who these
  people really are; nothing downstream invents a parallel identity for an already-cast NPC.
- **Turning points (3–5)** — beats that shift direction or tension, each committing its answer.
- **Tension curve** — pace build-up → rising action → climax → falling action → resolution. Flat too
  long bores; spiking too often burns out.
- **Engagement paths** — direct / indirect / avoidance / alternative. The open part: how the player
  might come at it, including how it escalates on its own if ignored.

## Level pacing — the major arc's advancement schedule

The **major arc** owns the campaign's advancement schedule; a minor arc leaves it to the major. Lay
out where the PC levels up along the arc's spine, so leveling is *planned* rather than forgotten (as
it is, no one hands out level-ups because no one owns them — this is where that ownership lives):

- **Milestone leveling, at a session's end.** A level-up lands when a session closes, never mid-scene.
- **Cadence: every 2–5 sessions, scaled by level.** Fast at low levels (~every 2), slower as the PC
  climbs (~every 4–5 by the teens). Pick the cadence for the PC's *current* level.
- **Prefer a beat, but keep the cadence regardless.** Land a level-up just after a major turning point
  when one is near — earned advancement feels best. But the cadence is a **floor that holds even when
  no beat is close**: never stall leveling for want of a story beat, and never bunch two together to
  catch up. Pace is maintained on the calendar and *decorated* by beats, not gated by them.
- **Commit each milestone** in the arc's *Level pacing* section: the target level and the session it's
  due, plus the beat it rides on when there is one. The dm pulls this when planning each session, and
  reconsiders it every apply-arcs pass.

## Craft principles

- **Every arc needs a hook** that draws the player in naturally — bond, curiosity, urgency, moral
  obligation. Never force engagement.
- **Flag the secrets and track who's in on them.** Turning points, the central truth, and villain
  motives are spoilers: `[hidden]` + `Known to:`. Cross-check the PC knowledge ledger
  (`characters/{slug}.knowledge.md`) so the arc starts from what the PC *actually* knows.
- **Leave room for agency** — open *paths*, never undecided *facts*.
- **Arcs can intersect.** Flag any cross-arc dependency so the dm can coordinate; intersections force
  harder choices and richer moments.

## Before you write

- **Gather:** `campaign/campaign.md` + `world/overview.md` (setting, tone, central conflict); `world/`
  + `INDEX.md` (entities to reuse, not duplicate); `characters/{slug}.md` + `{slug}.knowledge.md` (the
  PC's backstory, goals, and what they know); existing `arcs/` so a new arc complements rather than
  collides — and, for a minor arc, the **major** it hooks into.
- **Format** lives in **`canon-conventions`** and the `arc-design` template — load them; they own the
  file shape. Write `arcs/{slug}.md`, set `tier` and `hooks-into` in the frontmatter, register the arc
  in `INDEX.md` (Arcs) with its tier, link entities with `[[slug]]`, and flag spoilers `[hidden]` +
  `Known to:`.

## The bar

- Every load-bearing answer is fixed — no blanks, no "DM decides."
- Registered in `INDEX.md` with its `tier`, linked, and spoiler-flagged; a minor arc names the major
  in `hooks-into:` and cross-links it both ways.
- The only thing left open is the player's path.
