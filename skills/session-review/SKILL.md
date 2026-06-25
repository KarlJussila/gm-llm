---
name: session-review
description: Perform post-session analysis after a D&D session. Use after each session to evaluate what happened vs. what was planned, assess player engagement, identify narrative implications, and produce insights for arc adjustment and future planning.
---

# Session Review Skill

## Purpose

Reflect on what happened during a session and produce actionable insights for the campaign. This skill runs **between** sessions, as a fresh analytical pass — comparing planned events against actual outcomes, evaluating player engagement, and generating recommendations for future planning.

**Who runs this:** the `dm` agent (or a delegated `campaign-analyst`), *not* the session runner. The runner's job ends at writing the factual session log (`campaign/sessions/session-{N}.md`). This review reads that log fresh and turns it into strategy, which keeps the analytical pass uncoupled from a long play context and keeps the runner's role clean.

## Input

This skill reads:

- **Session plan** — `campaign/sessions/session-{N}-plan.md`
- **Session notes / actual events** — `campaign/sessions/session-{N}.md` (incl. its "Captured
  this session" checklist)
- **Character states** — `campaign/characters/*.md` (incl. the PC knowledge ledger
  `characters/{name}-knowledge.md`)
- **Significant items** — `campaign/world/items.md`
- **Documents recorded this session** — `campaign/documents/`
- **Active arcs** — `campaign/narrative/arcs/*.md`

## Review Structure

Write the review following this structure:

1. **Session summary** — What actually happened. A brief narrative of the session from start to finish.

2. **Plan vs. reality** — What was planned, what actually happened, and key deviations. Note which planned encounters occurred, which were skipped, and what emerged spontaneously.

3. **Player engagement analysis** — What did the player(s) lean into? What did they skip? What excited them? Where did energy dip? What moments held their attention?

4. **Narrative implications** — What threads were advanced? What new threads emerged? What was left unresolved?

5. **World state changes** — What changed in the world during this session? Locations visited, NPCs affected, items acquired, alliances shifted.

6. **Character changes** — What happened to PCs and NPCs? Level-ups, injuries, relationships changed, new motivations.

7. **Arc impact** — How did this session affect active narrative arcs? Which arcs advanced, stalled, or branched?

8. **Unresolved threads** — What needs attention in future sessions? Open questions, hanging plotlines, unresolved conflicts.

9. **Recommended arc adjustments** — Which arcs need adjustment based on this session? Suggest re-prioritization, timeline shifts, or new directions.

10. **Notes for next session** — What should the next session plan address? Specific threads to pick up, player interests to revisit, world events to resolve.

11. **Player feedback routing** — Read the log's "Player feedback" section. For each item, note the guidance you distilled and which `campaign/feedback/{target}.md` file you wrote it to (see `campaign/feedback/README.md`). This bakes the feedback in for next time without editing the framework.

## Review Principles

- **Extract structured state from the log.** By design, the runner's one mandatory live capture is
  a comprehensive session log; it defers most structured updates to you. Walk the log and make sure
  everything it records is reflected in its home: knowledge gained → the ledger
  (+`[hidden]`/`Known to:` flags), documents → `documents/`, improvised canon → `world/*.md`, item
  changes → `items.md` or the character sheet. Backfill whatever's missing while the session is
  fresh — and if the log itself is thin, that's a process failure worth flagging.
- **Knowledge check:** verify every thing the PC learned this session is in the knowledge ledger,
  and that the matching source facts were flipped (`[hidden]` → `[revealed: S<n>]`, `Known to:`
  updated, including any NPCs who learned something). Backfill anything the runner missed.
- Be honest about what worked and what didn't
- Focus on player engagement — what made them excited vs. disengaged?
- Track narrative momentum — are arcs advancing or stalling?
- Identify surprise moments — things that worked better than planned
- Flag any continuity issues that need addressing
- Note any world-building details established that need to be remembered

## File Output

Write the review to: `campaign/assessment/session-{N}-assessment.md`

## Tone

Reflective, analytical, forward-looking. This is a planning tool, not a critique. Focus on what to carry forward, not what went wrong.
