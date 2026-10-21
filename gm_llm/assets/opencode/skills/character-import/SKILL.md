---
name: character-import
description: Load when importing a player-provided character file during character creation.
---

# character-import

Turn a player's character file — an exported sheet, JSON, HTML, PDF text, a notes doc — into the PC
sheet, `characters/<slug>.md`, from the `pc-sheet` template. Extract; never invent. Where the source
doesn't state a value, leave it out: a gap the player fills beats a fabricated value.

## Read the structure

Exported sheets nest the real values: ability scores as entries keyed by an id, class and subclass
inside a `classes` array, proficiencies and feats in their own collections. The value you want is
rarely the first one you see, and a skim grabs the wrong one (an INT of 13 that's really 18). Parse
structured formats, JSON above all, with a command-line tool the system already has. Before
reporting a vital as missing, search the whole file for it; it's usually under a key you didn't
expect.

Use only what's installed: never install a package, and never write a parsing script. If careful
reading and the tools on hand can't crack the file, say so, and the details come from the player.

## What goes where

- **Frontmatter vitals** — race or lineage, class, subclass (only if the file has one), level,
  ability scores, pronouns. Fill every one the source supports.
- **`## Known capabilities`** — proficiencies, spells and abilities, feats, as far as the file lists
  them. Partial is fine.
- **Appearance, personality, backstory** — only if the source carries them, transcribed or condensed
  faithfully.

Write only the sheet. Fitting the backstory to the world, the DM-side hooks, the state file and the
ledger are done with the player, in `character-create`.

Report what you extracted, which required vitals the source lacked, and anything ambiguous or worth
the player confirming.
