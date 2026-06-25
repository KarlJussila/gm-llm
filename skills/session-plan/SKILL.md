---
name: session-plan
description: Prepare for an upcoming D&D session. Use before each session to create a flexible plan that accounts for likely player actions while leaving room for improvisation. Orchestrates the focused plan skills (encounter-plan, investigation-plan, npc-plan, pacing-plan) into one session plan.
---

# Session Plan (orchestrator)

This skill assembles a single session plan. It owns the plan's spine and output; the design-heavy
parts are focused skills you pull in as the session needs them.

## Player feedback — read first

Before planning, read `campaign/feedback/session-plan.md` if it exists. It holds accumulated,
player-specific guidance distilled from past sessions. Treat it as binding and let it override the
defaults here and in the sub-skills wherever they conflict.

## Purpose

Create a focused, flexible plan for a single D&D session that advances at least one active narrative
arc without over-planning. The output is a lightweight tactical guide — situations and expected
beats the runner can adapt in real time, not a rigid script.

## Input

Read before planning:

- **Campaign assessment** — latest campaign-assess output (world state, unresolved threads, tone).
- **Active arcs** — which arcs are in progress and where each stands.
- **World state** — current NPC positions, faction activity, time pressure, conditions.
- **Character states** — where each PC is, what they want, any immediate needs or injuries.
- **Last session's ending** — final scene, cliffhangers, open questions, unresolved tension.
- **PC knowledge ledger** — `characters/{name}-knowledge.md`: what the character knows, believes
  (including anything false), and is chasing. Plan reveals against this.
- **Next session number** — to name the output file.

## Assemble the plan

Write the plan in this order. Sections marked → delegate to a focused skill: load it, follow it for
that part, then fold the result into the plan.

1. **Opening State** — where the characters are right now, what just happened, the immediate
   circumstances (time, place, who's present, what's at stake). The session's anchor point.
2. **Likely Beats** — 3–5 things that will probably happen or need addressing, ranked by importance.
   The expected shape of the session, not guarantees.
3. **Encounter Seeds** → **`encounter-plan`**. 2–4 encounters as situations, not stat blocks.
4. **Discoveries & Investigations** → **`investigation-plan`**. Any revelation the session
   delivers — the clues, how they combine, and who assembles them.
5. **NPC Staging** → **`npc-plan`**. The NPCs in play — disposition, agenda, what they know, how
   they react to each other and the PC, and any concealed tells.
6. **Decision Points** — moments where player choice significantly affects the outcome. State the
   choice and what hangs on it; don't plan which option they pick.
7. **Contingencies** — for each likely beat, an if/then pair (*if the players do X, then Y*). Cover
   the two or three most probable deviations. Safety rails, not alternate campaigns.
8. **Pacing & Exits** → **`pacing-plan`**. Expected scope, natural stopping points, and a
   cliffhanger to build toward.

Not every session needs every sub-skill — skip the ones a given session doesn't call for (a quiet
social session may have no encounter seeds; a travel session may have no investigation). Pull a
skill when its content is in play.

## Cross-cutting principles

- **Cross-reference everything against canon (binding for every sub-skill).** Every NPC, clue,
  reveal, place, and stake in the plan must be consistent with established campaign knowledge — the
  world/NPC/faction files, active arcs, recorded documents, and the PC knowledge ledger. Don't
  invent facts that contradict canon, and don't hand any party knowledge they were never given.
- **Plan situations, not plots.** Problems and opportunities, not solutions.
- **Never plan player decisions.** Plan what the world does; let the player respond.
- **Keep 30–40% unplanned.** Leave room for improvisation and player-driven scenes.
- **Advance at least one active arc** — even small progress counts.
- **Flag knowledge on every clue and reveal.** Mark each `(known)` / `(new reveal)` / `(stays
  hidden)` against the ledger; never write a beat that assumes the PC knows something not in it.

The `dm` agent reviews and revises this plan after you return it — write it as a working draft to be
checked against canon and the arcs, not a final word.

## File Output

Write the completed plan to `campaign/sessions/session-{N}-plan.md` (create the directory if needed),
where `{N}` is the next session number.

## Handing off to the player — spoiler-free

**The plan you just wrote IS the spoiler.** The player has not read it and does not want it. When
you report back, do **not** summarize it, paraphrase it, or describe "the shape of it." Naming the
beats, the encounter seeds, the decision points, the exit hook/cliffhanger, NPC secrets, or what a
reveal will turn out to be — all of that is exactly the content the file exists to keep behind the
screen. A numbered "here's what happens" list is the failure mode, even when softened with "roughly"
or "the shape of."

The whole hand-off is **one or two sentences**, and contains only what the character already knows:

> Session 2 is planned and ready. You'll pick up right where you left off — [one spoiler-free line
> of the character's current situation, nothing they haven't already lived]. Start `dm-runner` when
> you want to play.

If you're tempted to add a clause about what's coming, what an NPC wants, what's behind the door, or
what the session "focuses on" — cut it. The test: would reading this sentence tell the player
something their character doesn't already know? If yes, it's a spoiler.

## Tone

Tactical, flexible, anticipatory — a working document for a DM about to run a session. Clear, direct,
ready to adapt. Avoid abstract theory; stay grounded in this campaign's specifics.
