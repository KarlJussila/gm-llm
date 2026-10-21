---
name: check-propagation
description: The narrative-checker's POST role — after a session's updates have been applied, judge whether what was played actually landed in canon and state.
---

# check-propagation — did what was played land?

POST role. A session's updates have been applied. Judge whether what the session established made
it from the record — the digest, `campaign/sessions/{N}/digest.md` — into canon and state. You
audit propagation, not design: don't re-judge authoring choices.

Code already checks the mechanics, so leave them alone: frontmatter, links that resolve, `INDEX.md`,
`named-only` stubs, `as-of` stamps, secret ids, and the reveal tags it flips from the ledger. Your
job is the part code can't judge — whether the content says what play established.

## The checks

1. **New and changed canon.** Each NPC, place, faction and item in *World canon* and *Items* has a
   file that says what play established about it — an improvised NPC filed with what the PC saw
   and heard, a changed entity revised where its truth changed.
2. **The arcs.** Each divergence in *Plan vs. actual* shows in the affected arc's body — turning
   points, answers, position — not just in its state file.
3. **The ledger.** Each fact in *Knowledge gained* is in the PC's knowledge ledger, a tagged secret
   with its `[learned:<id> S{N}]`.
4. **State.** Each entity whose situation changed has a snapshot that says so; `state/current.md`
   is where the session ended; the calendar and clocks moved as play moved them; the threads play
   opened, advanced or closed are reflected in `state/threads.md`.
5. **The PC.** Capabilities in *PC capabilities* are on the sheet, a level-up included; after a
   fight, the reaction triggers in *Combat reactions & tactics* are in the repertoire.

## Report

Per finding: what's missing, the digest entry it comes from, the file that should have it, and the
fix.
