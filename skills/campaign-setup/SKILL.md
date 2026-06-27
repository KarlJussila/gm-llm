---
name: campaign-setup
description: Initialize a new D&D campaign from an empty directory — scaffold the file structure, gather the player's vibe, build the world, character, and arcs as gated proposals, initialize all state, plan session 1, and hand off spoiler-free. Run by the dm. Use when starting a brand-new campaign.
---

# campaign-setup

## Player feedback — read first

Before running setup, read `campaign/feedback/campaign-setup.md` if it exists. It holds
accumulated, player-specific guidance distilled from past campaigns. Treat it as binding and let
it override the defaults here wherever they conflict.

## What this is

A new campaign goes from an empty directory to ready-to-play. The **creative stages** (vibe, world,
character, arcs) are collaborative and flexible — meet the player where they are. The **procedural
stages** (scaffold, gate, state-init, commit, hand-off) are an exact ordered algorithm — follow the
steps in order; don't skip or reorder them. You (the `dm`) run this and **author the canon yourself**
— load the craft skills (`world-build`, `arc-design`) and the format skill (`canon-conventions`) and
write the files directly. After authoring each bundle you **gate your own work** with the checklist
below. (The independent canon gate — the `narrative-checker` — comes online in the planning/runtime
phases; at init the gate is your own review.)

### Principles for the creative stages
- **Meet the player where they are.** One word ("noir") or a full pitch — take whatever they give.
- **Control dial** (offer at the world and character stages): *player-led* (they bring detail, you
  organize) · *collaborative* (default — you propose, they choose) · *DM-led / "surprise me"* (they
  give a vibe, you make the calls and present for a thumbs-up).
- **Spoiler discipline.** Present setting, tone, and surface situation. Never reveal secrets,
  twists, villains' true natures, or planned arcs — those go in files, not conversation.
- **Don't over-build before the character exists.** Build enough world to present a premise; save
  the major arcs until the character is made, so they can be personal.

### The gate (run this after authoring each bundle — stages 3, 5, 6)
After you write a bundle of canon, review it against this checklist and fix anything that fails:
- **No blanks.** No "DM decides / TBD / as needed" for any load-bearing fact (canon-conventions §1).
- **Registered.** Every created entity has an `INDEX.md` row; no entity is left unregistered.
- **No dangling links.** Every `[[slug]]` resolves; nothing references an unfiled entity.
- **No lingering `named-only`.** Anything the campaign will use is a full file, not a stub.
- **No duplicates.** No new entity overlaps an existing one in name or role (check `INDEX.md`).
- **Two-layer + flags.** Hidden truths are committed and flagged `[hidden]` + `Known to:`.
- **Consistent.** Nothing contradicts `campaign.md`, the world, or another file.

---

## Stage 0 — Scaffold the directory  *(exact steps; do first, before any conversation)*

1. **Campaign git repo.** If the project root is not a git repository, run `git init` there. This is
   the *campaign* repo (the framework has its own under `.opencode/`).
2. **Ignore the framework.** Ensure a root `.gitignore` contains `.opencode/`.
3. **Structure.** Create `campaign/` and its tree:
   `world/{npcs,factions,locations,items,regions}`, `arcs`, `state`, `characters`, `sessions`,
   `assessment`, `documents`, `feedback`.
4. **Conventions docs.** Copy `.opencode/templates/campaign/README.md` →
   `campaign/README.md` and `.opencode/templates/campaign/feedback/README.md` →
   `campaign/feedback/README.md`.
5. **Registry.** Create `campaign/INDEX.md` from the `canon-conventions` `INDEX` template — section
   headers only (PC, NPCs, Factions, Locations, Regions, Items, Arcs), empty tables.
6. **Empty state docs.** Create `campaign/state/current.md`, `calendar.md`, `threads.md`,
   `clocks.md` from their templates with `as-of: S1` and empty bodies. You populate them in Stage 7.

The first commit is Stage 8 — do not commit yet.

## Stage 1 — Vibe & control
If the player hasn't already said what they want, ask one open question: what kind of campaign do
they want — genre, vibe, premise, tone, or just a feeling, as vague or detailed as they like.

**First, mine what they've already told you.** Read their opening message and extract every
dimension they've already specified (genre, tone, themes, premise, scope, etc.). **Do not re-ask
what they've already answered** — it reads as not listening. Then judge how much they're handing you
vs. want to shape, and whether they want guiding questions or just want you to run with it.

## Stage 2 — Guided questions  *(optional — skip if the brief is already rich)*
Only if they want to be guided **or** left a dimension genuinely blank that you need. Ask **only**
about the gaps — never the dimensions they already covered — and let them defer any to you. The full
set, for reference: setting/world, tone, themes, stakes & scale, play-style mix, **content
boundaries** (lines & veils — honor everywhere after), power level (starting level, power fantasy).
If they gave a full pitch, skip straight to Stage 3 and only circle back for a missing essential
(e.g. content boundaries) — ideally folded into a single short confirm, not a questionnaire.

## Stage 3 — Build the world skeleton
1. Synthesize their answers into a premise and central conflict.
2. **Author the world yourself** — load `world-build` (craft) and `canon-conventions` (format):
   opening regions, key factions, a handful of NPCs, significant items, and the world-truth
   singletons (`overview`/`cosmology`/`history`) — enough to anchor a premise and hooks. Write the
   info files and register each in `INDEX.md`. Don't write state yet (Stage 7).
3. **Gate** what you wrote (checklist above).
4. Write a first-pass `campaign/campaign.md` (setting, tone, themes, stakes; record the content
   boundaries here). Build the surface; hold the arcs.

## Stage 4 — Present the premise & offer hooks  *(spoiler-free)*
Give the player a newcomer's-eye overview (setting, tone, surface situation). Offer **2–4 character
hooks** — each a role plus a tie into the situation. Invite them to take one, adapt it, or bring
their own.

## Stage 5 — Create the character
Load the **`character-create`** skill and follow it at the player's chosen control level. It writes
`characters/{slug}.md` (sheet), `characters/{slug}.state.md` (initial state),
`characters/{slug}.knowledge.md` (ledger), and registers the PC in `INDEX.md`. **Gate** the result.
Note the backstory canon and DM-side hooks it surfaces, for the next stage.

## Stage 6 — Weave the character into the world & arcs
1. **Fold in backstory canon.** For every new NPC/location/faction the backstory introduced, author
   and register it yourself (`world-build` + `canon-conventions`). **Gate.** Nothing the backstory
   names stays unfiled.
2. **Design the arc(s).** Load `arc-design` + `canon-conventions` and author at least one major arc
   woven into the character's backstory hooks (keep *how* spoiler-side); optionally minor arcs.
   Commit every answer (no "DM decides"). Write the arc design + its `INDEX.md` Arcs row. If the arc
   needs an entity that doesn't exist yet, author that entity first. **Gate.**
3. **Write each arc's initial state.** Create `arcs/{slug}.state.md` from the template at its
   starting status (usually `dormant`).
4. Finalize `campaign/campaign.md`.

## Stage 7 — Initialize state  *(exact steps — you are the single writer of all state)*
The canon now exists; write the opening snapshot, true as of the start of session 1:
1. **Entity state.** For every stateful entity you created, write `{slug}.state.md`
   (`as-of: S1`) from its starting-state facts: location, notable condition, what it's doing.
2. **`state/current.md`.** The opening scene: where the PC is, when, who's present, the immediate
   situation, and the opening hook. This is the runner's resume baseline.
3. **`state/calendar.md`.** The campaign's start date and any fixed calendar reference.
4. **`state/threads.md`.** The leads the PC starts with (from backstory + opening hooks).
5. **`state/clocks.md`.** Any time-pressure the arc set in motion at the start.
6. **Verify.** `INDEX.md` lists every entity; no `[[slug]]` dangles; nothing reads `named-only`.

## Stage 8 — Commit
Commit everything: `campaign: init`.

## Stage 9 — Plan session 1
Run the PRE-SESSION flow (see the `dm` agent): write the plan yourself (load `session-plan`), gate
it with the `narrative-checker`'s `check-plan` role, resolve any violations, write
`campaign/sessions/session-1-plan.md`, commit `campaign: session 1 plan`. **Do not** tell the player
to start `dm-runner` until this plan exists.

## Stage 10 — Hand off  *(spoiler-free)*
Confirm the campaign is ready and the character is placed. Recap only what the character would know
— the surface situation and the hook. **Do not** name or summarize the arc, list arc/plan files,
reveal secret motives, or mention twists or ticking clocks. Then tell the player to start
`dm-runner` when ready.
