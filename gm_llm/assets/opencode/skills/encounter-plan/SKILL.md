---
name: encounter-plan
description: Load when designing a session's encounter seeds — combat, social, exploration or puzzle.
---

# Encounter Design

Design 2–4 encounter seeds for the session as **situations, not stat blocks** — problems and
opportunities the runner can adapt around, not scripts.

## Each seed

- **Type** — combat, social, exploration, or puzzle.
- **Situation** — what is happening, who is involved, what is at stake.
- **Lever** — the one thing that makes it interesting: a hidden motive, a ticking clock, an
  environmental hazard, a moral trade-off.
- **Complication** — what could make it harder or messier than it looks.

## Principles

- **Cross-reference against canon.** Who's involved, where it happens, and what's at stake must be
  consistent with the world/NPC/faction files, active arcs, and the PC knowledge ledger. Use
  established places, NPCs, and threads rather than inventing disconnected material; an NPC in the
  seed behaves only on what they actually know.
- **Plan situations, not plots.** Create problems, threats, and opportunities — not solutions. The
  player will find solutions you never imagined.
- **Never plan the player's choice.** Plan what the world does and what's at stake; let the player
  decide how to respond.
- **Tie each seed to a thread.** Every encounter should touch an active arc, an NPC's agenda, or an
  unresolved hook — not exist for its own sake.
- **Leave room.** Seeds are starting conditions, not beat-by-beat plans; the runner improvises the
  middle.

## Combat seeds — the mechanical layer

A combat seed is still a **situation** (the four fields above), but it also has to arrive at the table
as loadable combatants — so a combat seed additionally commits:

- **Combatants** — which creatures and how many, each by `[[slug]]`. Named/recurring creatures carry
  their `## Stat block` in their NPC file; generic types live in the bestiary
  (`world/bestiary/{slug}.md`) — reference an existing one, or author a new bestiary file and register
  it for a creature the plan introduces. `start_encounter` loads from the file; never inline a stat
  block in the plan.
- **Starting positions** — where each combatant begins relative to the PC (distance, direction, and
  height if any) — the tracker's egocentric frame. Starting distance is a difficulty lever, not a
  detail; a ranged threat 60 ft off across open ground is a different fight from one 5 ft away.
- **Objective** — the win condition. Not always "kill them all": survive N rounds, reach the door,
  protect an NPC, hold until reinforcements. The objective shapes the fight more than any stat block.

**Shape the difficulty deliberately — load `combat-balance`.** This is a single-PC game, so action
economy (enemy count) dominates, not CR. `combat-balance` owns the levers (count, HP/damage, starting
distance, terrain, reinforcements, objective) and the two-way rounds-to-kill gut-check. **Lethality is
allowed — telegraphed and intentional, never an accidental PC death and never rescued by a fudge**: an
intelligent enemy presses or flees on its own nature, and the design bakes in any out, not a
mid-fight rescue reflex.

Combat *running* — the tactical flow, turn by turn — is a separate concern (the runtime combat skill);
here you seed the situation, commit the combatants and their footing, and set the intended difficulty.
