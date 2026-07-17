<!--
  BESTIARY entry — a generic, reusable creature TYPE (goblin, wolf, town guard), addressed by slug and
  referenced from encounter plans by [[slug]]. Register it in INDEX's Bestiary table.
  This is NOT a world entity: no `.state.md`, no secrets/agenda — a specific goblin's HP and position
  are tracker state, not canon. A *named*, unique creature with a story is an NPC instead
  (world/npcs/); if a bestiary creature earns a name and a role, promote it to an NPC file.
  Path: world/bestiary/{slug}.md. SRD content only. Commit every value; no "DM decides".
-->
---
slug: <kebab-slug>
name: <Creature Type>
type: creature
---

# <Creature Type>

## Description
<One or two lines: what it is, how it looks and behaves — enough for the runner to narrate and the
player to picture. Generic and reusable; nothing session-specific.>

## Stat block
<!-- The mechanical block start_encounter loads. Copy the format from stat-block.template.md. -->
