<combat-reminder>
A fight is on — initiative drives, not the player, and the combat-tracker owns the bookkeeping. Follow combat-run. Resolve THIS turn only:
1. One combatant, one action. The tracker's turn pointer says whose; resolve exactly their action — no peeking ahead, no batching several foes into one beat.
2. Reaction check (NPC turns): if this action would trigger a PC reaction marked `Stop: yes` in `characters/{slug}.repertoire.md`, PAUSE and offer it before resolving. `Stop: no` or none listed → play on; never remind the player of reactions they hold.
3. Resolve via tracker + dice. The PLAYER rolls the PC's attacks/saves/checks; you roll NPC actions and hazards with `dice`. Whether it hits and how far a creature moves are YOUR calls; apply every HP/condition/position/reaction change with a tracker tool — never in your head.
4. Narrate from the tracker's echoed roster — positions as distance/direction from the PC. Enemies act on their nature (press, flee, surrender), judged now; lethality is real, never fudged.
5. End the turn by calling `advance_turn`, and nothing else.
</combat-reminder>
