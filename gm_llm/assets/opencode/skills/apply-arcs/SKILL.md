---
name: apply-arcs
description: Load when reconciling an arc with a session that has just been played.
---

# apply-arcs — reconcile one arc with what was played

An arc is a living plan. After a session it is revised toward what actually happened — a real
revision of the design body, not a status bump. The record is the digest,
`campaign/sessions/{N}/digest.md`, chiefly *Plan vs. actual*, *Narrative*, *Threads* and
*Knowledge gained*. The arc is `campaign/arcs/{slug}.md` with its `{slug}.state.md`;
`canon-conventions` is the format.

Read `campaign/feedback/arc-design.md` if it exists: the player's standing guidance on how arcs
should feel, which wins over the defaults here.

## Two principles

**Played beats planned.** When the arc and the session disagree, the arc bends — revise the design,
never reality.

**Canon hardens on exposure.** A fact the player has seen or learned is locked: never retcon it.
What the player has learned is the knowledge ledger (`characters/{pc}.knowledge.md`) plus this
session's *Knowledge gained* — the ledger isn't updated for this session yet. A fact the player
hasn't met is yours to change, even a core one, if it makes a better story. Every load-bearing
answer stays committed; you may commit a better one.

## What to reconcile

Collect what the session did to this arc, then revise whatever it touched:

- **Turning points** — mark which landed, and in which session. Rewrite beats play altered, add the
  ones play created, rework or cut the ones it made impossible. Pending beats are free to redesign.
- **Committed answers** — keep what the player knows verbatim; recommit what play contradicted;
  answer every new load-bearing question play raised.
- **Key NPCs and factions** — update the arc's line for each whose role, want or held answer
  shifted, and link any the arc now leans on.
- **Premise, conflict and stakes** — revise toward the story play is telling. If play put a sharper
  conflict within reach and the player isn't locked into the old one, take it.
- **Tension curve** — where the arc sits now, and the remaining beats re-paced to how fast play is
  moving.
- **Engagement paths** — reset to the route the player took and what lies open from here.
- **Hooks** — if the arc fired into another arc or thread, or was fed by one, update the
  cross-reference on both sides.
- **Secrets** — tag any new secret with an id (`[hidden:<id>]`). Don't flip reveals yourself; the
  state pass records them and the orchestrator flips the tags.

Then add one line to the adjustment log — **S{N}:** what changed and the play that prompted it.

**Level pacing — the major arc only, every pass.** Mark any level-up delivered this session, then
re-project the schedule from the PC's current level and where the arc now sits: every 2–5
sessions, tighter at low levels. Never let it stall, and never bunch two level-ups to catch up.

## An arc the session didn't touch

If nothing in the session bears on the arc, leave its body alone — but the major arc still gets
its level-pacing pass.

## The state file

Every pass ends by rewriting `arcs/{slug}.state.md`, touched or not: status, turning points hit
(with sessions), position on the tension curve, and `as-of: S{N}`. The orchestrator reads that
stamp to know the arc was reconciled.

## Scope

This arc's design body and state file. New minor arcs, the threads dashboard, entity files, the
knowledge ledger and the `state/` dashboards are other steps.
