---
name: apply-canon
description: Load when filing a played session's new and changed entities, PC capabilities and documents into canon.
---

# apply-canon — file the session's new and changed canon

Everything play established about who or what things are becomes committed canon here: improvised
NPCs, new places, shifted truths. The record is the digest, `campaign/sessions/{N}/digest.md` —
chiefly *World canon*, *Items*, *Documents*, *PC capabilities* and *Combat reactions & tactics*.
`canon-conventions` is the format.

The player's feedback for `world-build` applies here too.

## Entities

Every NPC, location, faction, region and significant item play introduced or changed gets filed,
improvised ones included.

- **Check `INDEX.md` first.** Reuse an existing slug, turn a `named-only` stub into a full file, and
  extend a role-overlapping entity rather than create a near-twin.
- **A new entity** gets a full file from its template: every vital filled with a committed value,
  and an NPC's stats and abilities. Commit what the digest establishes, and decide now anything the
  story leans on that play left open.
- **A changed entity** — an allegiance flipped, a true nature surfaced — gets its file revised
  where the truth changed. Where it stands now is the state pass's job, not this one.

## The PC

- **Sheet.** Add to `## Known capabilities` every proficiency, spell, ability or feat the PC showed
  or gained that isn't listed. A level-up also updates the frontmatter (level, and any subclass or
  ability-score change).
- **Combat repertoire**, only after a fight. Add a `WHEN … THEN …` line for each reaction trigger
  the PC showed that isn't there yet, new entries at `Stop: no`, plus any signature tactic or rule
  wrinkle play surfaced. Apply any prompting preference the player stated by setting that
  reaction's `Stop:` as they asked — the toggle is theirs. Refine an entry rather than restate it,
  and set the file's `as-of` to this session.

## Documents

Write each verbatim handout to `campaign/documents/` with its exact text, and link it from the
entity it belongs to.

## Scope

Entity files, the PC's sheet and repertoire, and `documents/`. The arcs, every `.state.md`, the
`state/` dashboards and the PC's knowledge ledger are reconciled in their own steps.
