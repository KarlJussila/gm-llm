<!--
  STAT BLOCK — combat mechanics for the tracker. OPTIONAL; combat-relevant creatures only.
  One format, two homes:
   • a named/recurring creature → this section inside its NPC file (world/npcs/{slug}.md);
   • a generic, reusable creature type → its own bestiary file (world/bestiary/{slug}.md), which is
     mostly just this section (use bestiary.template.md).
  Either way the file is registered in INDEX and referenced from encounter plans by [[slug]] — never
  inline a stat block in the session plan.
  This is NOT the "Stats (rough sketch)" capability gauge — that is a rough social/exploration read;
  this is the mechanical block the runner runs the creature from and start_encounter loads.
  Commit every value (average HP, fixed bonuses); no "DM decides". SRD content only.
-->
## Stat block
- **HP:** <average, a fixed number — one fewer roll at the table>  ·  **AC** <n>  ·  **Speed** <30 ft; add fly/swim/climb + value if any>
- **Abilities** (score/check/save — all six, always): STR <n/±/±> · DEX <n/±/±> · CON <n/±/±> · INT <n/±/±> · WIS <n/±/±> · CHA <n/±/±>
  <e.g. STR 8/−1/−1 · CON 15/+2/+4 (save proficiency already baked into the save number). Any save
  or ability check can come up mid-fight, so all three are on the board and the model never derives a
  modifier from a score. Add a trailing "Skills:" note for any skill that beats the raw check —
  Athletics +5 (grapple/shove), Stealth, Perception — or omit it.>
- **Attacks:** <name, +<hit> to hit, reach/range <n> ft, <dice> <type> damage. One line per distinct
  attack. Add any rider inline: "on a hit, DC <n> CON save or poisoned (save ends)".>
- **Defenses & senses:** <resistances / immunities / vulnerabilities; senses like darkvision 60 ft — or "none notable">
- **Special:** <recharge abilities, spells, traits, and any REACTION the creature can spend off-turn
  — or "None." A reaction listed here is the creature's one-per-round reaction the tracker economy tracks.>
- **Tactics & nature:** <one line — how it fights (focus-fire, kite, swarm, guard a spot) and its
  temperament (presses, flees when hurt, fights to the death). Morale is judged in the moment, never a
  fixed HP threshold.>

<!-- Feeds start_encounter: the creature's name + HP become a roster entry; the ENCOUNTER SEED (in the
     session plan) supplies how many and where they start — count and starting distance/direction/height
     from the PC. The intrinsic block lives here; count and position are encounter-specific, set there. -->
