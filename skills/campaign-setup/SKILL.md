---
name: campaign-setup
description: Initialize a new D&D campaign from an empty directory — scaffold, gather the brief, build the world, character, and arcs, initialize all state, and commit `campaign: init`. A task-list-first runbook that loads focused skills (campaign-intake, world-build, character-create, arc-design). Run by the dm. Its scope ends at the init commit; planning session 1 and the hand-off are the dm's next steps.
---

# campaign-setup

## Read first

Read `campaign/feedback/campaign-setup.md` if it exists — accumulated, player-specific guidance from
past setups. Treat it as binding; let it override the defaults here.

You (the `dm`) run this and **author the canon yourself** — load the craft skills as each task calls
for them and write the files directly. After authoring a bundle you **gate your own work** with the
checklist below. (The independent canon gate — the `narrative-checker` — comes online in the
planning/runtime phases; at init the gate is your own review.)

## Build your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Scaffold the campaign directory
2. Gather the campaign brief (load `campaign-intake`)
3. Build the world skeleton (load `world-build`)
4. Present the premise & offer hooks
5. Create the character (load `character-create`)
6. Fold backstory canon into the world
7. Build the major arc around the character (load `arc-design`)
8. Add at least one minor arc (load `arc-design`)
9. Initialize all state
10. Commit `campaign: init`

## Principles
- **Meet the player where they are.** Their involvement is set during the brief (free-form vs.
  guided) — when they hand you a dimension, honor it; when they leave it open, decide it well.
- **Spoiler discipline.** In conversation, present setting, tone, and surface situation only. Secrets,
  twists, villains' true natures, and planned arcs go in files, never in what you say to the player.
- **The character comes before the major arc.** Build enough world to present a premise, then make
  the character — and *only then* develop the major arc, **around who they turned out to be**, so
  it's personal by construction rather than retrofitted.

## The gate (run after authoring each canon bundle — tasks 3, 5, 6, 7–8)
Review what you wrote against this checklist and fix anything that fails:
- **No blanks.** No "DM decides / TBD / as needed" for any load-bearing fact (canon-conventions §1).
- **Registered.** Every created entity has an `INDEX.md` row.
- **No dangling links.** Every `[[slug]]` resolves; nothing references an unfiled entity.
- **No lingering `named-only`.** Anything the campaign will use is a full file, not a stub.
- **No duplicates.** No new entity overlaps an existing one in name or role (check `INDEX.md`).
- **Two-layer + flags.** Hidden truths are committed and flagged `[hidden]` + `Known to:`.
- **Consistent.** Nothing contradicts `campaign.md`, the world, or another file.

---

### 1. Scaffold the campaign directory  *(exact steps; do first, before any conversation)*
1. **Campaign git repo.** If the project root is not a git repository, run `git init` there. This is
   the *campaign* repo (the framework has its own under `.opencode/`).
2. **Ignore the framework.** Ensure a root `.gitignore` contains `.opencode/`.
3. **Structure.** Create `campaign/` and its tree:
   `world/{npcs,factions,locations,items,regions}`, `arcs`, `state`, `characters`, `sessions`,
   `assessment`, `documents`, `feedback`.
4. **Conventions docs.** Copy `.opencode/templates/campaign/README.md` → `campaign/README.md` and
   `.opencode/templates/campaign/feedback/README.md` → `campaign/feedback/README.md`.
5. **Registry.** Create `campaign/INDEX.md` from the `canon-conventions` `INDEX` template — section
   headers only (PC, NPCs, Factions, Locations, Regions, Items, Arcs), empty tables.
6. **Empty state docs.** Create `campaign/state/current.md`, `calendar.md`, `threads.md`, `clocks.md`
   from their templates with `as-of: S1` and empty bodies (you populate them in task 9).

Don't commit yet — the commit is task 10.

### 2. Gather the campaign brief
Load **`campaign-intake`** and follow it: offer free-form or guided setup, capture the campaign's
dimensions to the player's chosen depth, and confirm content boundaries. It returns the brief; you
write it into canon in the next steps.

### 3. Build the world skeleton
1. Synthesize the brief into the world's premise and **central situation** — the tension the setting
   runs on (factions, pressures, what's at stake in the world). This is the canvas, not yet the PC's
   personal arc.
2. **Author the world yourself** — load `world-build` (craft) and `canon-conventions` (format):
   opening regions, key factions, a handful of NPCs, significant items, and the world-truth
   singletons (`overview`/`cosmology`/`history`) — enough to anchor a premise and hooks. Write the
   info files and register each in `INDEX.md`. Don't write state yet (task 9).
3. Write a first-pass `campaign/campaign.md` (setting, tone, themes, stakes; **record the content
   boundaries here**). Build the surface; **hold the arcs** — the major arc waits for the character.
4. **Gate** what you wrote.

### 4. Open character creation — present the world & hooks  *(spoiler-free)*
Give the player a newcomer's-eye overview (setting, tone, surface situation), then offer **2–4
character hooks** — each a role plus a tie into the situation — and invite them to take one, adapt it,
or bring their own. This **is** the opening of character creation: load `character-create` and carry
the player's response straight into it. Don't present the hooks, stop, and re-ask the same question
from a standing start.

### 5. Build the character
Follow `character-create` through to a finished, **player-confirmed** character: it delegates any file
they bring to `character-importer`, fills the missing vitals, and builds + confirms their backstory and
place in the world *with* them, then writes `characters/{slug}.md` (sheet) + `.state.md` +
`.knowledge.md` and the `INDEX` row. **Gate** the result. Note the backstory canon and DM-side hooks it
surfaces, for the next tasks.

### 6. Fold backstory canon into the world
For every new NPC/location/faction the backstory introduced, author and register it yourself
(`world-build` + `canon-conventions`). **Gate.** Nothing the backstory names stays unfiled.

### 7. Build the major arc — around the character
Load `arc-design` + `canon-conventions`. Now that you know who the PC is, develop the major arc's
central conflict *from* their backstory, goals, and bonds, so it's personal by construction (keep
*how* it exploits their past spoiler-side). `tier: major`. Commit every answer (no "DM decides");
author any entity the arc needs but doesn't exist yet.

### 8. Add at least one minor arc
A focused subplot that hooks into the major (`tier: minor`, `hooks-into:` the major, cross-linked both
ways) — a second live thread from session 1. Write each arc design + its `INDEX.md` Arcs row (with
`tier`), and finalize `campaign/campaign.md`. **Gate** the arcs.

### 9. Initialize all state  *(exact steps — you are the single writer of all state)*
The canon now exists; write the opening snapshot, true as of the start of session 1:
1. **Entity & arc state.** For every stateful entity and every arc, write `{slug}.state.md`
   (`as-of: S1`) from its starting facts: location/condition/what it's doing; arcs at their starting
   status (usually `dormant`).
2. **`state/current.md`.** The opening scene: where the PC is, when, who's present, the immediate
   situation, and the opening hook. This is the runner's resume baseline.
3. **`state/calendar.md`.** The campaign's start date and any fixed calendar reference.
4. **`state/threads.md`.** The leads the PC starts with (from backstory + opening hooks).
5. **`state/clocks.md`.** Any time-pressure an arc set in motion at the start.
6. **Verify.** `INDEX.md` lists every entity; no `[[slug]]` dangles; nothing reads `named-only`.

### 10. Commit
Commit everything: `campaign: init`.

## Done when
`campaign: init` is committed: the directory is scaffolded, the world / character / arcs are authored
and registered, all state is initialized, and the gate checklist passes across the board.
