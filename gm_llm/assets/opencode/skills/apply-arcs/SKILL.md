---
name: apply-arcs
description: Load when reconciling an arc with a session that has just been played.
---

# apply-arcs — carry an arc forward from what was played

An arc is the story you're telling: where it's going and what is true beneath it. After a session,
look at what play gave you — something the runner improvised that the arc must absorb, a thread the
player leaned into or turned away from, a sharper conflict within reach — and change the arc where
that makes the story better. Otherwise it stands. `arc-design` is what makes an arc strong; hold
the arc to it, and to the story and mix of play the player's brief (`campaign/campaign.md`) asks for.

What happened is the digest's to record, `campaign/sessions/{N}/digest.md`: chiefly *Plan vs.
actual*, *Narrative*, *Threads* and *Knowledge gained*. The arc is `campaign/arcs/{slug}.md` with
its `{slug}.state.md`; `canon-conventions` is the format. You edit the arc in place, and it never
records play.

## What play can change

- **Contradiction.** When the arc and the session disagree, the arc bends: rework the beats and
  answers play contradicted or made impossible. Revise the design, never reality.
- **The player's pull.** Bring forward what they leaned into. What they passed over can wait, or
  reach them another way.
- **What play opened.** A sharper conflict, a new ally or enemy, a consequence of what the PC did —
  take it when it makes a better story and the player isn't committed to the old one.

**Canon hardens on exposure.** A fact the player has seen or learned is locked: never retcon it.
What the player has learned is the knowledge ledger (`characters/{pc}.knowledge.md`) plus this
session's *Knowledge gained* — the ledger isn't updated for this session yet. A fact the player
hasn't met is yours to change, even a core one, if that makes a better story. Every load-bearing
answer stays committed.

## Editing the arc

- **Turning points** — as `arc-design` defines them. Pending ones are free to redesign; add one
  only where play opened a change of that size, never for a step the PC took toward one. A landed
  one changes only where play revealed it differently: then it says what the player saw.
- **Committed answers** — the truth beneath the story. Keep what the player knows verbatim, recommit
  what play contradicted, and answer every new load-bearing question play raised.
- **Opposition, NPCs and factions** — update anyone whose role, want or held answer shifted, and add
  any the arc now leans on, named and filed (`canon-conventions`). Someone still pushes against the
  PC, and they respond to what the PC did.
- **Premise, conflict, stakes, tension curve and engagement paths** — rewritten toward the story
  ahead, re-paced to how fast play is moving, with the kinds of play mapped onto what's left. Where
  the arc stands now is the state file's.
- **Hooks** — if the arc fired into another arc or thread, or was fed by one, update the
  cross-reference on both sides.
- **Secrets** — tag any new secret with an id (`[hidden:<id>]`). Don't flip reveals yourself; the
  state pass records them and the orchestrator flips the tags.

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
