---
name: apply-canon
description: The post-session canon pass — from the session digest, author and register every new or changed entity to the completeness contract, and route verbatim documents. Loaded by the dm during the post-session apply, per-entity, once the digest exists.
---

# apply-canon — file the session's new and changed canon

After a session, everything play established as a new or changed world-fact is brought into canon
properly: a real, complete file for each, registered so nothing is silently re-invented later. This
is where improvised NPCs, new locations, and shifted truths become committed canon.

## Read first
Read `campaign/feedback/world-build.md` if it exists — accumulated player guidance on world and
entity quality. Treat it as binding over the defaults here.

## Format and completeness are contracts — load canon-conventions
Load `canon-conventions` and follow it for all format (frontmatter, slugs, `[[links]]`, the `INDEX`
registry, `[hidden]`/`Known to:` flags). Every entity file must also meet the **completeness
contract**: the required `## Vitals` block for its type, filled with committed values, plus the
`## Stats` and `## Abilities` sections for an NPC. A file that leaves a required field blank or a
`<placeholder>` in place is not done.

## Input
- The **session digest** `campaign/sessions/session-{N}.md` — especially *World canon*, *Items*,
  *Documents*, *Secrets & awareness*, and *PC capabilities*.
- The **registry** `campaign/INDEX.md` — to reuse existing slugs and resolve `named-only` entries
  rather than duplicate.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. List the entities to file
2. Author each entity *(one task per entity — see below)*
3. Update the PC sheet
4. Route verbatim documents
5. Self-check completeness
6. Report

### 1. List the entities to file
From the digest's *World canon* and *Items*, list every new or changed NPC, location, faction,
region, and significant item — including anything improvised at the table. Cross-check each against
`INDEX.md`: reuse the existing slug if it's already there (and flesh out any `named-only` stub), and
extend a role-overlapping entity rather than spawn a near-duplicate. Then **add one `Author <slug>`
task per entity** and work them one at a time.

### 2. Author each entity (one task per)
- **New entity** — author the full info file `{slug}.md` from the matching `canon-conventions`
  template, to the completeness contract: fill the `## Vitals` for its type, and an NPC's `## Stats`
  + `## Abilities`. Commit every load-bearing fact the digest establishes, and decide + commit any
  the plot leans on that play left implicit — never "DM decides." Add its `INDEX` row.
- **Changed entity** — play shifted who or what it truly is (an allegiance flipped, a true nature
  surfaced): update the info file where the truth changed, keeping it complete; update its `INDEX`
  row if status or the one-line changed.
- In both, link every referenced entity as a `[[slug]]` and flag any secret `[hidden]` + `Known to:`.

### 3. Update the PC sheet
From the digest's *PC capabilities*, append to the PC sheet's `## Known capabilities` every
proficiency, spell, named/class ability, or feat the PC demonstrated or gained that isn't already
listed — cross-check the current sheet so nothing duplicates. If *PC capabilities* records a level-up,
update the `## Vitals` block (level, and any subclass or ability-score change it notes), keeping it
complete. The **sheet only** — the PC's `.state.md` and knowledge ledger are reconciled by the state
pass, not here.

### 4. Route verbatim documents
For any verbatim handout in the digest's *Documents* (a letter, inscription, quoted passage), write
the exact text to `campaign/documents/` and reference it from the entity it belongs to — don't
inline it.

### 5. Self-check completeness
- Every new or changed entity from the digest is filed — nothing load-bearing left `named-only` or
  unfiled.
- Every entity file meets the completeness contract (Vitals filled; an NPC's Stats + Abilities
  present).
- Any capability the digest shows the PC gaining is on the sheet; the PC's Vitals reflect a level-up.
- Every `INDEX` row points at a real file and vice-versa; no dangling `[[slug]]` links.

### 6. Report
Brief: **Result** (entities filed / updated, PC sheet changes), **Documents** routed, **Caveats**
(anything the digest left ambiguous).

## Boundaries
- Your scope is **entity info files (the PC sheet included), their `INDEX` rows, and `documents/`**.
  Leave arc bodies and every `.state.md` / global `state/*` snapshot — including the PC's `.state.md`
  and knowledge ledger — to their own reconciliation; your job here is the entity canon.
