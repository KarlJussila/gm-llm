---
name: check-propagation
description: Load when judging whether a session's updates landed in canon and state.
---

# check-propagation — did what was played land?

POST role. A session's updates have been applied. Judge whether what the session established made
it from the record — the digest, `campaign/sessions/{N}/digest.md` — into canon and state. You
audit propagation, not design: don't re-judge authoring choices.

Code already checks the mechanics, so leave them alone: frontmatter, links that resolve, `INDEX.md`,
`named-only` stubs, `as-of` stamps, secret ids, and the reveal tags it flips from the ledger. Your
job is the part code can't judge — whether the content says what play established.

Judge each fact in the home `canon-conventions` gives it under *What goes where*. Missing from its
home is a finding. Absent from anywhere else is not, and a fact copied onto another entity's file is
— most often a place's state recording who arrived, stayed or left. So is a file turned into a
record of play: an arc that recounts the session instead of designing the story ahead, a ledger
that logs what the PC did, planned or rolled.

## The checks

1. **New and changed canon.** Each NPC, place, faction and item in *World canon* and *Items* has a
   file that says what play established about it — an improvised NPC filed with what the PC saw
   and heard, a changed entity revised where its truth changed.
2. **The arcs.** Where play changed the story — contradicted a pending beat or answer, or made one
   impossible — the affected arc's design says so: its turning points, answers and the curve
   ahead, not just its state file. A beat that hasn't happened yet is still ahead; it needs no
   change.
3. **The ledger.** Each fact in *Knowledge gained* is in the PC's knowledge ledger under its
   subject, as that subject now stands: what it overturned replaced, not left beside it. A tagged
   secret carries its `[learned:<id> S{N}]`.
4. **State.** Each entity whose situation changed has a snapshot that says so; `state/current.md`
   is where the session ended; the calendar and clocks moved as play moved them; the threads play
   opened, advanced or closed are reflected in `state/threads.md`.
5. **The PC.** Capabilities in *PC capabilities* are on the sheet, a level-up included; after a
   fight, the reaction triggers in *Combat reactions & tactics* are in the repertoire.

## Report

Per finding: what's missing, the digest entry it comes from, the file that should have it, and the
fix.
