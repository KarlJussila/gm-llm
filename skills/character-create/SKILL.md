---
name: character-create
description: Collaboratively create a player character — concept, mechanical details, placement in the world, and backstory — then write the character sheet. Use during campaign setup, or later when a new PC joins. Produces campaign/characters/{name}.md and surfaces DM-side hooks for arcs.
---

# character-create

## Player feedback — read first

Before building a character, read `campaign/feedback/character-create.md` if it exists. It holds
accumulated, player-specific guidance distilled from past sessions. Treat it as binding and let it
override the defaults here wherever they conflict.

## Purpose

Build a player character with the player and root them in the established world, so the character
feels like they belong and gives the DM threads to pull. This is a narrative-integration tool, not
a rules engine: record mechanical details as the player provides them and help translate a concept
into a fitting class/race/background if they want it — but leave actual building, balancing, and
leveling to the player's preferred D&D tools.

## Control dial

Match the player's preference (the same dial as `campaign-setup`):
- **Player-led** — they hand you a finished character; you place them in the world and tidy the
  sheet.
- **Collaborative** (default) — they bring a concept; you propose options and build it together.
- **DM-led / "surprise me"** — they give a seed (or one of the offered hooks) and let you flesh it
  out, presenting choices for approval.

## Steps

1. **Concept.** Get the character idea — as much or as little as they offer. If little, propose a
   few options drawn from the world's hooks and archetypes.
2. **Mechanical details.** Capture race, class, background, level, ability scores, and notable
   features/equipment *as the player provides them*. Offer to suggest a class/race/background that
   fits the concept if they want help. Don't invent rules or balance encounters — just record.
3. **Placement in the world.** Decide where they're from, why they're here now, and their ties to
   existing locations, factions, and NPCs. Keep it consistent with established lore; where the
   backstory needs new people or places, create that canon and note it so it can be folded into
   the world files.
4. **Backstory.** Build it at the player's chosen depth: origin, formative events, bonds, goals,
   flaws, and any secrets. Keep it consistent with the world and its tone/content boundaries.
5. **DM-side hooks.** Distill 1–3 threads from the backstory the DM can later weave into arcs
   (an unresolved loss, a hunted past, a rival, a debt). These are the seams the major arc hooks
   into — keep how they'll be used spoiler-side; don't tell the player the plan.

## Seed the knowledge ledger

Also create `campaign/characters/{name}-knowledge.md` — the live record of what the character
knows (see `campaign/README.md` → *Knowledge & awareness*). Seed it from the backstory and
starting situation:

- **Knows** — what they'd hold as true at the start: their own history, their goal, and the
  general, openly-known facts a person of their background would have about the world.
- **Believes (may be wrong)** — any assumptions or secondhand beliefs they carry that the world
  may later complicate.
- **Open questions** — the mysteries they're already aware of and motivated to chase.

Keep it to what the *character* knows — not the campaign's secrets. Those stay `[hidden]` in the
world and arc files.

## File output

Write `campaign/characters/{name}.md` and `campaign/characters/{name}-knowledge.md`. Follow the
established sheet structure (an existing sheet is the template): Basic Information & stats (as
provided), Appearance, Personality (traits, flaws, ideals, bonds), Backstory, Connections to the
World, Character Hooks for the DM, and any Mechanical Notes. Surface the new world canon and
DM-side hooks back to setup/review so the world and arcs can absorb them.

## Tone

Collaborative and curious. The character is the player's; your job is to make them fit the world
and give the story something to grab onto.
