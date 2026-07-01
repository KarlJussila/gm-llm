---
name: character-create
description: Collaboratively create a player character with the player — concept, mechanical details, placement in the world, backstory — then write the PC's three files (sheet, state, knowledge ledger) and register the PC. Use during campaign setup, or later when a new PC joins. Player-facing, so it is run by the dm (a primary), never a subagent. Records DM-side story hooks in the sheet and folds in any backstory canon the world must absorb.
---

# character-create

## Player feedback — read first

Before building a character, read `campaign/feedback/character-create.md` if it exists. It holds
accumulated, player-specific guidance distilled from past sessions. Treat it as binding and let it
override the defaults here wherever they conflict.

## Who runs this, and format

This skill is **player-facing** — it interviews the player — so it is run by the **dm** (a primary).
A subagent cannot use it (subagents can't touch the player). The dm authors the PC files here: the
state file and knowledge ledger always, and the sheet — either from scratch or by completing the
draft the `character-importer` extracted from an imported file (step 2).

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

Use your `todowrite` tool to create entries for steps 1–5 plus Confirm, Write the three PC files, Fold backstory canon, and **Finish — call `task_complete`**, then work them in order. That last entry is not optional: the process always ends with the `task_complete` tool call.

1. **Open — hooks and how do you want to make your character?** This is the skill's opening beat.
   At campaign setup the DM has just given the player a world overview — build directly on it: devise
   **2–4 character hooks** (each a role plus a tie into the situation, spoiler-free), present them,
   and in the **same message** offer the character-creation choice: they can **take or adapt one of
   these hooks**, **bring their own** (point you at any file — a sheet export, PDF, JSON, HTML dump,
   notes doc, whatever they've got), or **build one together** from scratch at their chosen control
   level. Hand off to the player and wait. Continue from whatever they say; don't re-ask from a standing start.
2. **Hand the file to `character-importer`.** For any real character file they point you at — a
   JSON/HTML/PDF/sheet export *or* a multi-section notes doc — **delegate to the `character-importer`**
   subagent (give it the source path and the target sheet path `characters/{slug}.md`), even though you
   could open it yourself. The importer parses the whole structure properly — a glance at a D&D Beyond
   export misses the nested stats, class, and subclass — and keeps a big file out of your context; it
   writes what it can into the sheet and reports which vitals the source lacked. (A one-line "level 5
   elf wizard" needs no importer. No file → gather the vitals by talking.)
3. **Fill the vital gaps.** Ask the player for any **vital** detail still missing after the import:
   race/lineage, class (and subclass, if they have one), level, ability scores, pronouns. Just the
   vitals — don't make them recite their whole proficiency and spell list; the rest gets documented
   as it surfaces in play.
4. **Backstory & place in the world — with the player, not behind their back.** If the file carried a
   backstory that already fits the world, use it; otherwise ask for a rough idea of who they were, or
   build one together. Then **propose** how they fit the setting — where they're from, why they're here
   now, ties to existing locations, factions, and NPCs (`[[slug]]` links) — and run it past them.
   Anything you infer, modify, or fill in (a hometown, a faction tie, a reason they came to the
   frontier) is a **proposal to confirm**, not a fact to commit silently. Ask the questions that matter
   to them and adjust to their answers. Where the backstory needs **new** people or places, note them
   (see *Hand back to setup*) — don't author full world files here; the dm folds those in afterward
   (its *fold backstory canon* step).
5. **DM-side hooks.** Distill 1–3 threads from the backstory the story can later hook into (a loss,
   a hunted past, a rival, a debt) and record them in the sheet's DM-side hooks. Keep *how* they'll
   be used spoiler-side — record the seams, not the plan.

## Confirm before you commit
Don't write the files or finish until the player has **seen and okayed** the finished character:
their vitals, their place in the world, the ties you've drawn, and anything you filled in for them.
Match the weight to how much you added: a quick "here's where I've slotted you in — good?" if they
handed you a complete sheet, a fuller walk-through if you built a lot together. The character is
theirs to sign off on; don't run ahead of what they've seen.

When you talk to the player — here and anywhere — use plain names, not canon notation: write "Erasmus
Venn," never the `[[erasmus-venn]]` link. The `[[slug]]` syntax belongs in the files, not on their screen.

## Write the three PC files

- **`characters/{slug}.md`** (sheet) — from `pc-sheet.template` (or completing the `character-importer`
  draft): the **`## Vitals`** block (race/lineage, class, subclass if any, level, ability scores,
  pronouns — every line a committed value), **`## Known capabilities`** (the proficiencies/spells/
  abilities/feats you gathered — partial is fine, it grows in play), then appearance, personality,
  backstory, connections (`[[slug]]`), DM-side hooks, links.
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

## Fold backstory canon

For every new NPC/location/faction the backstory introduced, author and register it yourself
(`world-build` + `canon-conventions`). **Gate.** Nothing the backstory names stays unfiled.

## Finish — call `task_complete`

The last step, every time. Once the PC is confirmed by the player, the three files are written and
registered, and any backstory canon is folded in, **call the `task_complete` tool**. That signals
the character is done and hands control back — the rest of setup proceeds on its own. Do **not** build
or plan anything beyond the character yourself, and do **not** tell the player to start or launch
anything; the table opens when it's ready.

## Tone
Collaborative and curious. The character is the player's; your job is to make them fit the world and
give the story something to grab onto.
