---
name: campaign-setup
description: Initialize a new D&D campaign through a guided, staged flow — from the player's target vibe (vague or specific) to a spoiler-free premise, a collaboratively built character, and at least one major arc woven into that character's backstory. Use when starting a brand-new campaign.
---

# campaign-setup

## Player feedback — read first

Before running setup, read `campaign/feedback/campaign-setup.md` if it exists. It holds
accumulated, player-specific guidance distilled from past campaigns. Treat it as binding and let
it override the defaults here wherever they conflict.

## Purpose

Take a new campaign from nothing to ready-to-plan: gather what the player wants, design the world,
present a premise and character hooks, build the character with them, and seed the arcs — without
spoiling the surprises you're planting.

## Principles for the whole flow

- **Meet the player where they are.** They may hand you one word ("noir") or a full pitch. Take
  whatever they give; only ask for more if they want to be asked.
- **Offer a control dial** at the world stage and the character stage:
  - *Player-led* — they bring detailed ideas; you organize and fill gaps.
  - *Collaborative* (default) — back-and-forth, you propose, they choose.
  - *DM-led / "surprise me"* — they give a vibe and hand you the wheel; you make the calls and
    present results for a thumbs-up.
  Gauge which they want (ask if unsure) and flex each stage accordingly.
- **Spoiler discipline.** Present setting, tone, and the surface situation. Never reveal the
  secrets, twists, villains' true natures, or the arcs you're planning. Those go in the files,
  not in conversation. (See the `session-run` spoiler rules — same boundary.)
- **Don't over-build before the character exists.** Build enough world to present a premise and
  offer hooks. Save the major arcs until the character is made, so they can be personal.

## Stage 0 — Scaffold

Do this first, before any conversation, if the campaign doesn't exist yet. It makes the working
directory self-contained — the system builds its own structure and git repo.

1. **Git repo.** If the project root is not a git repository, run `git init` there. This is the
   *campaign* repository (the framework has its own under `.opencode/`).
2. **Ignore the framework.** Ensure a root `.gitignore` exists containing `.opencode/`, so the
   campaign repo never tracks the framework.
3. **Structure & conventions.** Create the `campaign/` directory and copy the templates from
   `.opencode/templates/campaign/` into it — this provides `campaign/README.md` (the directory
   map and capture conventions) and `campaign/feedback/README.md` (the feedback routing guide).
   The remaining directories (`world/`, `sessions/`, `characters/`, `narrative/arcs/`,
   `documents/`, `assessment/`) are created lazily as files are written into them.

The first commit happens at Stage 7.

## Stage 1 — Vibe & control

Ask one open question: what kind of campaign do they want? Genre, vibe, a specific premise, a
tone, or just a feeling — as vague or as detailed as they like. Sense how much they're handing you
vs. want to shape, and whether they'd like to be asked guiding questions or just let you run.

## Stage 2 — Guided questions (optional)

Only if the player wants guidance or gave you little. Walk a standard set, letting them answer or
defer any to you ("you choose"):

- **Setting / world** — genre, level of magic/tech, scope (a town, a kingdom, planes).
- **Tone** — gritty ↔ heroic, light ↔ dark, grounded ↔ mythic, comedic ↔ serious.
- **Themes** — what the campaign is *about* (loss, ambition, found family, corruption…).
- **Stakes & scale** — personal, local, or world-shaking? Solo adventurer to epic?
- **Play-style mix** — combat / roleplay / investigation / exploration balance.
- **Content boundaries** — lines (never include) and veils (keep off-screen). Ask plainly; honor
  them everywhere afterward.
- **Power level** — starting level and the kind of power fantasy (underdog, rising hero…).

## Stage 3 — Design the world skeleton

Synthesize their answers into a premise and a central conflict. Then (the `campaign/` structure
already exists from Stage 0 — see `campaign/README.md` for the layout):
1. Delegate world-building to **`world-builder`** — opening locations, key factions, a handful of
   NPCs, and any significant item — enough to anchor a premise and hooks.
2. Write a first-pass `campaign/campaign.md` (overview: setting, tone, themes, stakes). Record
   the content boundaries here too.
Build the surface; hold the arcs.

## Stage 4 — Present the premise & offer hooks

Give the player a **spoiler-free** overview: the setting, the tone, and the situation as a
newcomer would perceive it. Then offer **2–4 character hooks or archetypes** that fit this world
and give them a foothold — each a role plus a tie into the situation (e.g., "a local whose village
sits closest to the spreading blight," "a scholar chasing a rumor only this region can answer").
Invite them to take one, adapt it, or bring their own concept.

## Stage 5 — Create the character

Load the **`character-create`** skill and follow it, at the control level the player chose. It
produces `campaign/characters/{name}.md` (concept, mechanical details, world placement, backstory,
DM-side hooks) and seeds `campaign/characters/{name}-knowledge.md` with what the character knows at
the start.

## Stage 6 — Weave the character into the world & arcs

Now that the character exists:
1. Fold the character's backstory canon into the world (hometown, mentor, rival, patron, etc.) —
   delegate to **`world-builder`** to add/adjust locations, NPCs, and factions so the world
   already contains the people and places the backstory references.
2. Delegate to **`arc-designer`**: create **at least one major arc** — and optionally minor arcs
   or hooks — that weave into the character's backstory hooks and goals, so the central conflict
   is personal. Keep *how* the arcs use their backstory spoiler-side.
3. Finalize `campaign/campaign.md`.

## Stage 7 — Commit

Commit everything: `campaign: init`.

## Stage 8 — Prepare the first session, then hand off (spoiler-free)

1. **Plan session 1 before handing off.** Run the PRE-SESSION flow (see the `dm` agent's
   lifecycle): delegate to `session-planner` to write `campaign/sessions/session-1-plan.md`,
   review it against the arc, and commit `campaign: session 1 plan`. Do **not** tell the player to
   start `dm-runner` until this plan exists — the runner reads the plan and has nothing to run
   without it.
2. **Give a spoiler-free hand-off.** Confirm the campaign is ready and their character is placed,
   and recap only what their character would know — the surface situation and the hook that pulls
   them in. **Do not** name or summarize the arc, list the arc/plan files, reveal faction secret
   motives, or mention twists, buried truths, or ticking clocks — those live in files the player
   has chosen not to read. Then tell them to start `dm-runner` when ready to play.
