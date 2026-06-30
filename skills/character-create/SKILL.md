---
name: character-create
description: Collaboratively create a player character with the player — concept, mechanical details, placement in the world, backstory — then write the PC's three files (sheet, state, knowledge ledger) and register the PC. Use during campaign setup, or later when a new PC joins. Player-facing, so it is run by the dm (a primary), never a subagent. Surfaces DM-side hooks for arcs and any backstory canon the world must absorb.
---

# character-create

## Player feedback — read first

Before building a character, read `campaign/feedback/character-create.md` if it exists. It holds
accumulated, player-specific guidance distilled from past sessions. Treat it as binding and let it
override the defaults here wherever they conflict.

## Who runs this, and format

This skill is **player-facing** — it interviews the player — so it is run by the **dm** (a primary).
A subagent cannot use it (subagents can't touch the player). Because the dm runs it, the dm authors
all three PC files here, including the state file (state is the dm's to write).

**Load `canon-conventions` and follow it for format**, and build from the PC templates:
`pc-sheet.template` → `characters/{slug}.md`, `pc-state.template` → `characters/{slug}.state.md`,
`pc-knowledge.template` → `characters/{slug}.knowledge.md`. The PC is a registered entity — add its
row to `INDEX.md` (PC).

This is a **narrative-integration tool, not a rules engine**: record mechanical details as the
player provides them, and help translate a concept into a fitting class/race/background if they
want it — but leave building, balancing, and leveling to the player's preferred D&D tools.

## Control dial

Match the player's preference:
- **Player-led** — they hand you a finished character; you place them in the world and tidy the sheet.
- **Collaborative** (default) — they bring a concept; you propose options and build it together.
- **DM-led / "surprise me"** — they give a seed (or one of the offered hooks) and let you flesh it
  out, presenting choices for approval.

## Steps

1. **Concept.** Get the character idea — as much or as little as they offer. If little, propose a
   few options drawn from the world's hooks and archetypes.
2. **Mechanical details.** Capture race, class, background, level, ability scores, and notable
   features/equipment *as the player provides them*. Offer to suggest a fit if they want help.
   Don't invent rules or balance encounters — just record.
3. **Placement in the world.** Decide where they're from, why they're here now, and their ties to
   existing locations, factions, and NPCs — as `[[slug]]` links, consistent with established lore.
   Where the backstory needs **new** people or places, note them (see *Backstory canon*) — don't
   author full world files here; the dm folds those into the world afterward (its *fold backstory
   canon* step).
4. **Backstory.** Build it at the player's chosen depth: origin, formative events, bonds, goals,
   flaws, secrets. Keep it consistent with the world and its tone/content boundaries.
5. **DM-side hooks.** Distill 1–3 threads from the backstory the arcs can later hook into (a loss,
   a hunted past, a rival, a debt). Keep *how* they'll be used spoiler-side — record the seams, not
   the plan.

## Write the three PC files

- **`characters/{slug}.md`** (sheet) — from `pc-sheet.template`: stats as provided, appearance,
  personality, backstory, connections (`[[slug]]`), DM-side hooks, mechanical notes, links.
- **`characters/{slug}.state.md`** (initial state) — from `pc-state.template`: starting location,
  any notable condition, key starting items, the opening objective. This is the session-1-start
  snapshot. **Don't track HP, spell slots, or money** — the player owns granular resources; record
  only what's narratively worth remembering.
- **`characters/{slug}.knowledge.md`** (ledger) — from `pc-knowledge.template`, seeded from the
  backstory and starting situation:
  - **Knows** — what they'd hold as true at the start: their own history, their goal, and the
    general, openly-known facts a person of their background would have about the world.
  - **Believes (may be wrong)** — assumptions or secondhand beliefs the world may later complicate.
  - **Open questions** — the mysteries they're already aware of and motivated to chase.

  Keep it to what the *character* knows — **never** the campaign's secrets. Those stay `[hidden]`
  in the world and arc files (canon-conventions §5); this ledger is their mirror, flipped only when
  a secret is actually revealed in play.

Then **register the PC** in `INDEX.md` (PC section).

## Hand back to setup

Surface to the dm, for the world and arcs to absorb:
- **Backstory canon** — every new NPC/location/faction the backstory introduced, so the dm authors
  and registers it (nothing the backstory names stays unfiled).
- **DM-side hooks** — the 1–3 threads, so the dm can make an arc personal to this PC.

## Tone
Collaborative and curious. The character is the player's; your job is to make them fit the world and
give the story something to grab onto.
