---
name: character-import
description: Parse a player-provided character file (any format — exported sheet, JSON, HTML, PDF text, notes) into the PC sheet's structured format. Extract every detail the file actually contains, never invent, and report which required vitals it lacked. Loaded by the dm during character creation to parse an imported character file.
---

# character-import

## Read first
Read `campaign/feedback/character-import.md` if it exists — accumulated guidance on how this player's
sheets tend to be laid out (e.g. where they keep subclass). Treat it as binding.

## What this does
Turn a player's character file — an exported sheet, JSON, HTML, PDF text, a notes doc, anything — into
the campaign's PC sheet. You **extract**: take what the file genuinely contains and write it into the
sheet's structure. You do **not** invent — if the source doesn't state a stat, class, or feature,
leave it out; a gap the dm fills with the player beats a fabricated value.

## Read it thoroughly — don't skim
Open the file and work through its **structure**, carefully. Exported sheets (D&D Beyond and the like)
**nest** the real values — ability scores as a list of entries keyed by an id, class and subclass
inside a `classes` array, proficiencies and feats in their own collections — so the value you want is
rarely the first one you see, and a careless read drops it or grabs the wrong one (an INT recorded as
13 when it's really 18). Navigate the actual structure; don't eyeball the top of the file and guess.
**Before you report a required vital as missing, search the whole file for it** — it is almost always
there, under a key you didn't expect.

For a structured format — JSON above all — **parse it with a tool** rather than reading it by eye: a
command-line parser pulls the nested class, subclass, and stat values precisely, where reading
top-to-bottom misses them. You have bash — use whatever parsing tools the system already provides.

**But only what's already there** — never install anything (no `pip` / `npm` / `apt` / `brew` or any
package manager) and never write your own parsing code or scripts. If careful reading plus the tools
on hand still can't crack the file, don't engineer around it: stop, and say plainly in your report
that you were unable to parse it, so the dm gets those details from the player directly.

## Map it onto the sheet
Load `canon-conventions` and build from the `pc-sheet` template. Write what you find into:
- **`## Vitals`** — Race / lineage, Class, Subclass *(only if the file has one)*, Level, Ability
  scores, Pronouns. This is the completeness contract; fill every line the source supports.
- **`## Known capabilities`** — Proficiencies, Spells & abilities, Feats, as far as the file lists
  them. Partial is fine — this section grows in play.
- **Appearance / Personality / Backstory** — only if the source carries them; transcribe or condense
  faithfully, don't embellish.

Leave a field blank (or omit an optional line) wherever the source is silent.

## Stay in your lane
You write **only the sheet**, with what the file gave you. Integrating the backstory into the world,
distilling DM-side hooks, and authoring the state file and knowledge ledger are the dm's job, done
with the player — not yours.

## Report
Hand back: what you extracted, **which required vitals the source lacked** (so the dm knows exactly
what to ask the player for), and anything ambiguous, illegible, or worth the player confirming.
