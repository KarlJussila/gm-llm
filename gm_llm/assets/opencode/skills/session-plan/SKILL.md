---
name: session-plan
description: Load when planning an upcoming session.
---

# Session Plan

A session plan is a working document for the DM about to run the session: a flexible plan that
advances at least one arc, commits every load-bearing fact, and leaves the player's path open. It
goes in `campaign/sessions/{N}/plan.md`; `canon-conventions` is the format.

## The one rule

**Commit every load-bearing fact. Leave open only the player's path.** Every identity, every reveal,
the answer behind a mystery, what a check yields, what an NPC knows — fix it now. Never write "DM
decides", "TBD", "as needed" or "the runner creates" for something the session leans on; that punt
is what forces invention at the table. For anything the session needs, take the arc's committed
answer if it has one, else existing canon, else decide it now and file it. Ambient colour (a passing
vendor's name) is the runner's to improvise.

## What to work from

- The last session's digest `campaign/sessions/{N-1}/digest.md`, if there was one: what happened,
  where the plan was left, what the player leaned into.
- `campaign/state/threads.md` — the open leads.
- The arcs and their state files: where each stands, its committed answers, the major arc's level
  pacing.
- `campaign/state/current.md`, `calendar.md` and `clocks.md`.
- The PC's sheet, state and knowledge ledger — plan every reveal against what the character
  already knows.

## What a plan holds

Include what this session calls for; a quiet social session may have no encounters, a journey no
investigation.

- **Opening state** — where the PC is, what just happened, who's present, what's at stake. The
  anchor, from `state/current.md`.
- **Likely beats** — three to five things that will probably happen or need addressing, ranked.
- **Encounter seeds** — situations first; a combat seed also commits its combatants, footing and
  objective for the tracker. `encounter-plan` covers designing them.
- **Discoveries** — any revelation the session can deliver: the clues, how they combine, the
  committed answer, and whether the player or the character puts it together.
  `investigation-plan` covers this.
- **NPCs** — the ones in play, by `[[slug]]`: disposition, agenda, what they know, how they react,
  their tells. Their identities come from the arc and canon, never re-invented. `npc-plan` covers
  staging them.
- **Decision points** — moments where the player's choice changes the outcome: the choice and what
  hangs on it, never which way they'll go.
- **Contingencies** — if/then pairs for the two or three likeliest deviations.
- **Pacing and exits** — expected scope, natural stopping points, a cliffhanger to build toward.
  `pacing-plan` covers this.
- **Advancement** — whether a level-up lands at the end of this session, from the major arc's level
  pacing and the PC's `level`: an explicit yes-to-level-N, with the beat it rides on if one is near,
  or no. A due level-up lands at the close even without a big beat.

**New entities.** Every entity the plan introduces gets a full file from its template, not a stub.
Check `INDEX.md` for name and role overlap first, and reuse or differentiate rather than make a
near-twin.

**Before you finish,** check the plan against the arc (no identity or reveal contradicts it, no
parallel invented for an NPC it already cast), against the ledger (mark each clue known, a new
reveal, or staying hidden; no beat assumes the PC knows what it doesn't), and for blanks.

## Principles

- **Plan situations, not plots** — problems and opportunities, not solutions.
- **Never plan the player's decisions.** Plan what the world does.
- **Leave 30–40% unplanned** for improvisation and the scenes the player drives. The openness is
  the path, never the facts.
- **Advance at least one arc**, even a little.
- **The plan ends at the table.** No "post-session updates" or "what to file afterward" section:
  canon is reconciled from what actually happened, and nothing that updates files reads the plan.

## Telling the player

The plan is the spoiler. The whole hand-off is a sentence or two of what the character already
knows — "Session 2 is ready; you pick up where you left off, [one line of the character's current
situation]." Don't summarise or hint at beats, encounters, NPC secrets or the exit hook, and don't
tell the player to start anything; the session opens on its own.
