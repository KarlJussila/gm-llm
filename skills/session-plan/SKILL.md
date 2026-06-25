---
name: session-plan
description: Prepare for an upcoming D&D session. Use before each session to create a flexible plan that accounts for likely player actions while leaving room for improvisation. Produces session plans with beats, encounter seeds, and contingencies.
---

## Player feedback — read first

Before planning, read `campaign/feedback/session-plan.md` if it exists. It holds accumulated,
player-specific guidance distilled from past sessions. Treat it as binding and let it override the
defaults here wherever they conflict.

## Purpose

Create a focused, flexible plan for a single D&D session that advances at least one active narrative arc without over-planning. The output is a lightweight tactical guide — a set of situations and expected beats that the DM can adapt in real time, not a rigid script.

## Input

Read the following before generating the plan:

- **Campaign assessment** — latest campaign-assess output (world state, unresolved threads, tone).
- **Active arcs** — which arcs are in progress and where each stands.
- **World state** — current NPC positions, faction activity, time pressure, environmental conditions.
- **Character states** — where each PC is, what they want, any immediate needs or injuries.
- **Last session's ending** — final scene, any cliffhangers, open questions, unresolved tension.
- **PC knowledge ledger** — `characters/{name}-knowledge.md`: what the character currently knows,
  believes (including anything false), and is chasing. Plan reveals against this.
- **Next session number** — to name the output file correctly.

## Session Plan Structure

Write the plan in this order:

### 1. Opening State

Where are the characters right now? What just happened? What are the immediate circumstances — time of day, location, who is present, what is at stake? This is the anchor point for the session.

### 2. Likely Beats

List 3–5 things that will probably happen or need to be addressed this session. These are the expected shape of the session — not guarantees, but educated guesses based on current threads and player behavior patterns. Rank them by importance.

### 3. Encounter Seeds

Describe 2–4 encounter seeds as **situations, not stat blocks**. Each seed should specify:

- **Type** — combat, social, exploration, or puzzle.
- **Situation** — what is happening, who is involved, what is at stake.
- **Lever** — the key thing that will make this interesting (a hidden motive, a ticking clock, an environmental hazard, a moral trade-off).
- **Complication** — what could make it harder or messier than it looks.

### 4. Decision Points

Identify moments where player choice will significantly affect the outcome of the session. State what the choice is between and what hangs on it. Do not plan which option the players will pick.

### 5. Contingencies

For each likely beat, write an if/then pair: *If the players do X, then Y happens.* Cover the two or three most probable deviations from the expected flow. Keep these short — they are safety rails, not alternate campaigns.

### 6. Exit Conditions

Define one or two natural stopping points the session can land on. For each, state:

- **What would make this a satisfying stopping point** — a resolved beat, a new question, a moment of rest.
- **A cliffhanger to build toward** — if the session has momentum, what revelation, threat, or turn would leave players eager for next time.

## Planning Principles

- **Plan situations, not plots.** Create problems, threats, and opportunities — not solutions. The players will find solutions you never imagined.
- **Never plan player decisions.** Plan what the world does. Let players decide how to respond.
- **Keep 30–40% of the session unplanned.** Reserve space for improvisation, player-driven scenes, and unexpected turns. A session that is 100% planned leaves no room for the table's best moments.
- **Every session should advance at least one active arc.** Even small progress counts — a conversation that shifts a relationship, a clue that recontextualizes a mystery, a setback that raises the stakes.
- **Start and end with energy.** The opening sets the tone. The closing creates anticipation. Spend effort on both.
- **Track what needs resolution and what can wait.** Some threads are urgent. Others can simmer. Use this plan to sort them.
- **Flag knowledge on every clue and reveal.** For each piece of information in the plan, mark
  whether the PC `(known)` already has it, `(new reveal)` could learn it this session, or it
  `(stays hidden)`. Never write a beat that assumes the PC knows something not in their ledger.
  Where useful, note which NPCs are aware of a secret, so their behavior in the scene is consistent.

## File Output

Write the completed session plan to:

```
campaign/sessions/session-{N}-plan.md
```

Where `{N}` is the next session number. If the directory does not exist, create it.

## Tone

Write with a tactical, flexible, anticipatory tone. This is a working document for a DM about to run a session — clear, direct, and ready to be adapted on the fly. Avoid abstract theory; stay grounded in the specific details of this campaign.
