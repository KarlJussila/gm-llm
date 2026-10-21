---
name: check-plan
description: Load when reviewing a draft session plan before it is finalized.
---

# check-plan

The plan arrives inline in your brief, after a block of canon already read for you. The canon lint
has checked the campaign files' structure; it doesn't read the plan. A plan that advances an arc
differently than you would is fine. Flag only these:

- **Unresolved references.** Every entity, place, item or faction the plan relies on exists as a
  full file, and the plan links it by `[[slug]]`.
- **The arc contradicted.** Every identity, reveal or answer the plan supplies matches the arc's
  committed answers, and the plan pulls those answers where the session raises the question rather
  than re-deciding them. An invented second identity for a role the arc already cast is a
  contradiction.
- **Unearned knowledge.** No beat assumes the PC knows what the knowledge ledger doesn't record,
  and each reveal is marked correctly as known, a new reveal, or staying hidden.
- **Overlap.** No entity the plan introduces duplicates an existing one's name or role; say whether
  to merge or differentiate, naming the existing file.
- **Blanks.** No load-bearing fact is left open — "DM decides", "TBD", "as needed", "the runner
  creates". Only the player's path stays open.

For each finding give the correct fact or arc answer where there is one, its source file, and the
fix.
