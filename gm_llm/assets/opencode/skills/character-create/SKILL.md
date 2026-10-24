---
name: character-create
description: Load when creating a player character with the player and fitting them into the campaign.
---

# character-create

This interviews the player, so the `dm` runs it; a subagent can't. It's narrative integration, not a
rules engine: record mechanics as the player gives them, without auditing where they come from, and
help turn a concept into a fitting class, race or background if they want — building, balancing and
levelling stay with their D&D tools. `canon-conventions` is the format.

Match how much the player wants to drive: a finished character to place and tidy; a concept to build
together (the default); or a seed to flesh out yourself, with choices put to them for approval.

## The conversation

1. **Open with hooks and the choice.** Building on the world as built — its places, factions and
   people — devise two to four spoiler-free character hooks, each a role plus a tie into the situation. In the same message,
   offer the choice: take or adapt a hook, bring their own character file (a sheet export, PDF, JSON,
   notes — anything), or build one together. Then wait, and continue from whatever they say.
2. **Import a file** with `character-import`. A one-line "level 5 elf wizard" needs no import.
3. **Fill the vitals** still missing: race or lineage, class (and subclass, if any), level, ability
   scores, pronouns. Only the vitals — the full proficiency and spell list surfaces in play.
4. **Backstory and place in the world.** Use a backstory that already fits; otherwise ask for a
   rough idea or build one together. Then propose how they fit the setting — where they're from, why
   they're here, and whom and what they already know among the existing places, factions and NPCs. Anything you infer or fill in (a
   hometown, a faction tie, a reason they came) is a proposal to confirm, never a fact to commit
   silently.
5. **DM-side hooks.** Distil one to three threads from the backstory the story can later pull — a
   loss, a hunted past, a rival, a debt. Record the seams, not the plan.

Don't write the files until the player has seen and okayed the finished character: vitals, place in
the world, the ties you drew, and anything you filled in. Match the weight to how much you added — a
quick "here's where I've slotted you in — good?" for a complete sheet, a fuller walk-through for one
you built together. On their screen use plain names ("Erasmus Venn"), never `[[slugs]]`.

## The four PC files

From the PC templates in `canon-conventions`:

- **`characters/<slug>.md`, the sheet** — every required frontmatter vital committed;
  `## Known capabilities` (partial is fine, it grows in play); then appearance, personality,
  backstory, connections, DM-side hooks.
- **`characters/<slug>.state.md`** — starting location, any notable condition, key starting items,
  the opening objective, stamped `as-of: S0`. Never HP, spell slots or money; the player tracks
  those.
- **`characters/<slug>.knowledge.md`, the ledger** — by subject, what someone of their background
  knows at the start of the world, the region, and the people and places around them (at least
  what the primer says), what they believe that may be wrong, and the open questions they're
  motivated to chase. Never the campaign's
  secrets: those stay tagged in the world and arc files, and enter the ledger only when play reveals
  them.
- **`characters/<slug>.repertoire.md`** — the PC's reaction-eligible moves as
  `WHEN <trigger> THEN <reaction>` lines: an opportunity attack always, plus any reaction spell or
  feature the sheet shows (Shield, Counterspell, Hellish Rebuke). Seed each at `Stop: no` — the toggle
  is the player's to set in play, so don't ask about it now. Add a tactic or build wrinkle (a reach
  weapon, a feat that changes opportunity attacks) only where the sheet makes it explicit.

Every person, place or faction the backstory introduced gets its own file (`create_entities`);
nothing it names stays unfiled.
