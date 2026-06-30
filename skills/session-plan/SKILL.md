---
name: session-plan
description: Prepare an upcoming D&D session — a flexible plan that advances at least one arc, commits every load-bearing fact, and leaves the player's path open. Orchestrates the focused plan skills (encounter-plan, investigation-plan, npc-plan, pacing-plan). Loaded by the dm, which authors the plan inline and then gates it with the narrative-checker's check-plan role.
---

# Session Plan

This skill assembles a single session plan. It owns the plan's spine and output; the design-heavy
parts are focused skills you pull in as the session needs them.

## Player feedback — read first

Before planning, read `campaign/feedback/session-plan.md` if it exists. It holds accumulated,
player-specific guidance distilled from past sessions. Treat it as binding and let it override the
defaults here and in the sub-skills wherever they conflict.

## Format — load canon-conventions

**Load `canon-conventions`** and follow it: reference every entity by `[[slug]]`, and when the plan
needs an entity that doesn't exist yet, author it as a **full file** and register it in `INDEX.md`
(see step 9). The plan itself goes in `campaign/sessions/session-{N}-plan.md`.

## The one rule

> **Commit every load-bearing fact in the plan. Leave open only the player's path.**

Every identity, reveal, the answer behind a mystery, what a check yields, what an NPC knows — fix it
now. The only thing you leave open is what the *player* decides. Never write "DM decides", "TBD",
"as needed", or "the runner creates" for a load-bearing fact — that punt is what forces fabrication
at the table. **Fact-resolution priority** for anything the session needs:
1. the **arc's** committed answer, if it has one — pull it;
2. else existing **canon** (`INDEX.md` → the file);
3. else **decide it now** and author it as new canon (step 9).

Trivial ambient color (a passing vendor's name) is the runner's to improvise — don't pre-author it.

## Step 1 — Create your task list

Use your `todowrite` tool to create these entries, then work them in order:

1. Opening State
2. Likely Beats
3. Encounter Seeds *(→ `encounter-plan`)*
4. Discoveries & Investigations *(→ `investigation-plan`)*
5. NPC Staging *(→ `npc-plan`)*
6. Decision Points
7. Contingencies
8. Pacing & Exits *(→ `pacing-plan`)*
9. Author & register new entities
10. Self-check (arc / ledger / overlap / no-blanks)

Skip a sub-skill's section if the session doesn't call for it (a quiet social session may have no
encounters; a travel session no investigation). Pull a skill when its content is in play.

## Input — read before planning
- **Situation report** — the latest `campaign-assess` output (world state, threads, tone).
- **Active arcs** — `campaign/arcs/{slug}.md` + `.state.md`: where each stands and its committed answers.
- **Current state** — `campaign/state/current.md`, `calendar.md`, `threads.md`, `clocks.md`.
- **Entities in play** — their info/state files (via `INDEX.md`).
- **PC** — `characters/{slug}.md` + `.state.md`, and the ledger `characters/{slug}.knowledge.md`
  (what the PC knows/believes/chases — plan reveals against this).

## What each entry entails

1. **Opening State** — where the PC is now, what just happened, the immediate circumstances (time,
   place, who's present, what's at stake). The session's anchor; pull it from `state/current.md`.
2. **Likely Beats** — 3–5 things that will probably happen or need addressing, ranked. The expected
   shape, not guarantees.
3. **Encounter Seeds** → **`encounter-plan`**. 2–4 encounters as situations, not stat blocks.
4. **Discoveries & Investigations** → **`investigation-plan`**. Any revelation the session delivers
   — the clues, how they combine, **the committed answer**, and who assembles it.
5. **NPC Staging** → **`npc-plan`**. The NPCs in play — disposition, agenda, what they know, how
   they react, concealed tells. Each by `[[slug]]`; their identities are the arc's/canon's, never
   re-invented.
6. **Decision Points** — moments where player choice significantly affects the outcome. State the
   choice and what hangs on it; **don't** plan which option they pick.
7. **Contingencies** — for the likely beats, if/then pairs (*if the player does X, then Y*). Cover
   the two or three most probable deviations. Safety rails, not alternate campaigns.
8. **Pacing & Exits** → **`pacing-plan`**. Expected scope, natural stopping points, cliffhanger.
9. **Author & register new entities** — for every entity the plan introduces (resolution step 3
   above), write a **full info file** via the matching `canon-conventions` template (not a stub),
   register it in `INDEX.md`, and **check it against existing entities for name/role overlap** — if
   it duplicates something, reuse or differentiate, don't spawn a near-twin. Free license to invent
   the world forward; no license to invent thin or colliding entities.
10. **Self-check** before handing off — verify, and fix:
    - **Honor the arc:** no identity/reveal contradicts the arc or invents a parallel for an
      already-cast NPC; the plan pulls the arc's answers.
    - **Ledger:** every clue/reveal flagged `(known)` / `(new reveal)` / `(stays hidden)` against
      `characters/{slug}.knowledge.md`; no beat assumes the PC knows what it doesn't.
    - **Overlap:** every new entity dedup-checked (step 9).
    - **No blanks:** no "DM decides / TBD / as needed" anywhere.

## Cross-cutting principles
- **Plan situations, not plots.** Problems and opportunities, not solutions.
- **Never plan player decisions.** Plan what the world does; let the player respond.
- **Keep 30–40% unplanned.** Leave room for improvisation and player-driven scenes — that openness
  is the *path*, not the *facts*.
- **Advance at least one active arc** — even small progress counts.
- **The plan ends at the table.** Plan only what's needed to *run* the session. Don't write a
  "post-session updates" or "what to file afterward" section: canon is reconciled from what
  *actually* happened, never from a checklist written in advance, and nothing that updates files
  reads the plan.

## File output
Write the plan to `campaign/sessions/session-{N}-plan.md`, where `{N}` is the next session number.

## Handing off to the player — spoiler-free

**The plan you just wrote IS the spoiler.** The player has not read it and does not want it. When
you report back, do **not** summarize it, paraphrase it, or describe "the shape of it." Naming the
beats, encounter seeds, decision points, the exit hook/cliffhanger, NPC secrets, or what a reveal
will turn out to be — all of that is exactly what the file exists to keep behind the screen. A
numbered "here's what happens" list is the failure mode, even softened with "roughly."

The whole hand-off is **one or two sentences**, containing only what the character already knows:

> Session 2 is planned and ready. You'll pick up right where you left off — [one spoiler-free line
> of the character's current situation]. Start `dm-runner` when you want to play.

The test: would reading this sentence tell the player something their character doesn't already
know? If yes, it's a spoiler — cut it.

## Tone
Tactical, flexible, anticipatory — a working document for a DM about to run a session. Clear,
direct, grounded in this campaign's specifics.
