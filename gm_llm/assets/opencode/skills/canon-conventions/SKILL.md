---
name: canon-conventions
description: Load before you create or edit any file under campaign/.
---

# canon-conventions

How the campaign is recorded, so every file has the same shape. What to write is the job of
whatever task you're on; how to write it is here. Templates for every file are in `templates/`
beside this skill, and `examples/` holds a filled NPC and its state file.

## The one rule

**Commit every load-bearing fact when you write it; leave open only what the player decides.** An
NPC's true allegiance, what a search turns up, the answer behind a mystery — decide it now and
write it down. Never write "DM decides", "TBD" or "as needed". Ambient colour (a passing vendor's
name) is the live DM's to improvise; it doesn't need a file.

## Layout

```
campaign/
├── INDEX.md                 generated registry — read it, never edit it
├── campaign.md              premise and spoiler-free pitch
├── world/
│   ├── overview.md  cosmology.md  history.md     world-truth documents
│   ├── npcs/ factions/ locations/ regions/ items/ concepts/    {slug}.md (+ {slug}.state.md)
│   └── bestiary/            {slug}.md — reusable creature types, no state
├── arcs/                    {slug}.md + {slug}.state.md
├── characters/              {slug}.md (sheet) + .state.md + .knowledge.md + .repertoire.md
├── state/                   current.md  calendar.md  threads.md  clocks.md
├── sessions/<n>/            plan.md  transcript.md  notes.md  digest.md
└── documents/               verbatim handouts — letters, inscriptions, quoted text
```

**State files.** NPCs, factions, arcs and the PC always have a `{slug}.state.md` beside the info
file: where it stands *now*, as of the end of a session (`as-of: S<n>`; `S0` before the first). Locations, regions, items
and concepts get one only when they have live state that changes in play. State files are frozen
during play and rewritten between sessions; the transcript is the live record in between. State is
the now, not the history, and never HP, slots or coin — the player tracks those.

**The PC** has four files: the sheet, its state, the knowledge ledger (what the *character* knows,
believes and wonders) and the combat repertoire (its reactions and when to offer them).

**Verbatim text** — a letter, an inscription, a quoted passage — goes in `documents/` and is linked
from the entity it belongs to.

## Frontmatter

Every entity, PC sheet and arc opens with YAML frontmatter, and that is where its identity lives:

```yaml
---
slug: lysa-fenn          # kebab-case of the canonical name, same as the file name, never changes
name: Lysa Fenn
type: npc                # pc | npc | faction | location | region | item | concept | creature | arc
status: active           # active | dormant | hidden | dead | destroyed | resolved
summary: Saltgate harbormaster; secret rebel informant     # one clause
# …then the type's vitals — the template lists them
---
```

Each type's template lists its vitals (an NPC's `full-name`, `race`, `pronouns`, `age`, `role`,
`affiliation`; a location's `kind`, `region`, `setting`, `controlled-by`, `scale`; and so on). Fill
every one with a committed value. An NPC also needs a `## Stats (rough sketch)` and an
`## Abilities` section; a creature that can fight needs a `## Stat block` (see
`stat-block.template.md`).

`INDEX.md` is built from this frontmatter. To register an entity, write its file; to change its
summary or status, edit its frontmatter.

## Links

Refer to a registered entity or arc as `[[slug]]`, at its first mention in each file. Threads and
clocks are rows in `state/threads.md` and `state/clocks.md`, and their `slug` column is linkable the
same way. Every link must resolve: a link to something that doesn't exist means either the thing is
real and needs a full file, or it was invented loosely and the link should go. To find what refers
to an entity, grep for `[[slug]]`.

**Before creating an entity, check `INDEX.md`** for an existing slug or a role-overlapping entity,
and extend that one instead of creating a near-duplicate.

## Secrets

Any secret, hidden motive, true nature or planned reveal is tagged where it lives, with an id
unique across the campaign and a `Known to:` line naming the in-world parties who know it:

```
- [hidden:fenn-informant] Lysa feeds the harbor patrol's rotation to the [[harbor-cell]].
  Known to: [[lysa-fenn]], harbor-cell leadership.
```

Tag the secrets, not the surface — openly apparent details need no tag.

**When the PC learns a secret,** record it once, in the knowledge ledger, ending the line with
`[learned:<id> S<n>]`. The orchestrator then turns the home tag into `[revealed:<id> S<n>]` and adds
the PC to its `Known to:`. Don't edit either of those yourself.

## Named-only

A thing named in play but not yet written up may exist briefly as a stub with `status: named-only`.
It never survives a between-session pass: whoever is writing canon turns it into a full file.

## Before you finish

The orchestrator runs a lint after your work and sends back anything it finds: missing or unfilled
frontmatter, a slug that doesn't match its file, a missing state file or `as-of`, an empty required
section, a link that resolves nowhere, a secret without an id, a `named-only` stub. Check for those
yourself first.
