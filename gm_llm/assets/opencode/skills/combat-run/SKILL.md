---
name: combat-run
description: Load when a fight is about to start.
---

# combat-run — running the fight

Your table rules hold in a fight: the player rolls their character's attacks, saves and checks, and
spoilers stay behind the screen.

## Entering the fight

Roll initiative — the player rolls the PC's, `dice` rolls the foes' — then call
`start_encounter(roster, scene)` with the roster in that order. Each combatant's name and HP come
from its stat block (the `## Stat block` in a named creature's file, or its `world/bestiary/<slug>.md`
entry); the count and starting position (distance, direction and height from the PC) come from the
plan's encounter seed. The PC has id `pc`.

An unplanned fight with no prepared blocks: stat the foes on the fly, and load `combat-balance`
before you set the numbers. An accidental fight still gets an intended, telegraphed difficulty.

## Each turn

Once the encounter starts, initiative drives instead of the player. The orchestrator sends one
combatant's turn at a time in `<combat-turn>`; on the PC's turn it carries the player's action.

1. **One combatant, one action.** The tracker's turn pointer says whose turn it is; never batch
   several foes into one beat.
2. **Offer stopping reactions first.** If the action would trigger a PC reaction marked `Stop: yes`,
   pause and offer it before resolving (below).
3. **Resolve through the tracker and dice.** Roll NPC actions and hazards with `dice`. Every HP,
   condition, position and reaction change is a tracker call.
4. **Narrate from the roster** the tracker echoes, positions as distance and direction from the PC
   ("the archer's 30 ft NE, up on the ledge").
5. **End the turn with `advance_turn`.**

After an NPC turn the player confirms it or interjects. An interjection arrives in
`<combat-reaction>` with the tracker rolled back to the start of that combatant's turn; replay the
turn with the reaction folded in.

## The tracker bookkeeps; you judge

The tracker holds HP, positions, conditions, initiative, round and turn, reactions and timers. Never
keep any of it in your head: ask the tracker and tell the tracker.

- **The tracker:** arithmetic, turn order, a named condition's effect text, duration countdowns,
  geometry.
- **You:** whether an attack hits, how far a creature can actually move (terrain, obstacles, a
  grapple), whether an enemy presses or flees, whether a reaction applies. The tracker applies the
  displacement you decide; it is not a rules engine.

## Reactions

A reaction is spent off-turn, interrupting someone else's — the easiest thing in a fight to miss.
Each reaction in the PC's repertoire (`characters/<slug>.repertoire.md`) carries a player-owned
`Stop:` toggle:

- **`Stop: yes`** — before the triggering action resolves, pause and offer it. The player reacts and
  it folds in, with nothing rolled back.
- **`Stop: no`** (the default) — play on. The player rations their reaction and interjects if they
  want it.

Never remind the player of reactions they hold: offering one unbidden is a tell and a tax on the
fight. The one exception: the first time the player uses a reaction, you may ask once whether to make
it stopping from now on. The toggle decides whether to pause, never whether the reaction is worth
using. The interjection replay is the net for a pause you missed, not a substitute for pausing.

## Living combatants, real lethality

Whether an enemy presses, retreats, surrenders or dies fighting is its nature, judged in the moment:
an intelligent foe flees when a thinking creature would, a cornered beast doesn't, a broken mook
drops its weapon and runs. Never reduce this to an HP threshold. An NPC at 0 HP isn't automatically
dead; `set_dead` is your call.

When a fight turns against the PC, don't reach for an escape hatch. The tracker keeps the death-save
tally, and three failures is a dead character. The place to shape the danger was the design,
telegraphed before the dice, not a rescue mid-swing.

## Ending the fight

When the fight is decided — the foes dead, fled or surrendered — call `end_encounter()` and return to
player-driven play. End on the beat it's won or lost, without mop-up rounds.
