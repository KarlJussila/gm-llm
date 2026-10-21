---
name: encounter-plan
description: Load when designing a session's encounter seeds — combat, social, exploration or puzzle.
---

# encounter-plan — encounter seeds

Design two to four seeds as situations the runner can adapt around, not scripts.

## Each seed

- **Type** — combat, social, exploration or puzzle.
- **Situation** — what is happening, who is involved, what is at stake.
- **Lever** — the one thing that makes it interesting: a hidden motive, a ticking clock, a hazard, a
  moral trade-off.
- **Complication** — what could make it harder or messier than it looks.

Tie each seed to an active arc, an NPC's agenda or an open hook, and build it from established
places, NPCs and threads. An NPC in a seed acts only on what they know. A seed is starting
conditions; the runner improvises the middle.

## Combat seeds

A combat seed also arrives at the table as loadable combatants:

- **Combatants** — which creatures and how many, each by `[[slug]]`. A named or recurring creature
  carries a `## Stat block` in its NPC file; a generic type lives in the bestiary
  (`world/bestiary/<slug>.md`) — reuse one, or author a new bestiary file for a creature the plan
  introduces. `start_encounter` loads from the file, so never inline a stat block in the plan.
- **Starting positions** — distance, direction and height from the PC. Distance is a difficulty
  lever: a ranged threat 60 ft off across open ground is a different fight from one 5 ft away.
- **Objective** — the win condition, not always "kill them all": survive three rounds, reach the
  door, protect an NPC, hold until help comes.

Load `combat-balance` to set the difficulty on purpose.
