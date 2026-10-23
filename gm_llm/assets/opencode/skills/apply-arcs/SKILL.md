---
name: apply-arcs
description: Load when reconciling an arc with a session that has just been played.
---

# apply-arcs — reconcile one arc with what was played

An arc is a living plan. After a session it is revised toward what actually happened — a real
revision of the design body, not a status bump — and it stays a plan: where the story is going and
what is true beneath it. What play did is the digest's; the arc takes only what changes the story.
The record is the digest, `campaign/sessions/{N}/digest.md`, chiefly *Plan vs. actual*,
*Narrative*, *Threads* and *Knowledge gained*. The arc is `campaign/arcs/{slug}.md` with its `{slug}.state.md`;
`canon-conventions` is the format.


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

- **Turning points** — rewrite pending beats play altered, rework or cut the ones it made
  impossible, and add a beat where play opened a new shift in the story; a step the PC took is not
  a beat. A landed beat changes only where play revealed it differently: then it says what the
  player saw. Pending beats are free to redesign.
- **Committed answers** — keep what the player knows verbatim; recommit what play contradicted;
  answer every new load-bearing question play raised. Each is the truth beneath the story, not a
  note of what play established.
- **Key NPCs and factions** — update the arc's line for each whose role, want or held answer
  shifted, and add any the arc now leans on, named and filed (`canon-conventions`).
- **Premise, conflict and stakes** — revise toward the story play is telling. If play put a sharper
  conflict within reach and the player isn't locked into the old one, take it.
- **Tension curve** — the remaining beats re-paced to how fast play is moving; where the arc sits
  now is the state file's.
- **Engagement paths** — the ways in that lie open from where the story now stands.
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
(with sessions), position on the tension curve in a line, and `as-of: S{N}`. The orchestrator reads that
stamp to know the arc was reconciled.

## Scope

This arc's design body and state file. New minor arcs, the threads dashboard, entity files, the
knowledge ledger and the `state/` dashboards are other steps.
