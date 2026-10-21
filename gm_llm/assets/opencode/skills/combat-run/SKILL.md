---
name: combat-run
description: Load when a fight is about to start — entering it with the tracker, running each initiative turn, reactions, morale and lethality, and ending it.
---

# combat-run — running the fight

Your table rules hold in a fight too: the player rolls their character's attacks, saves and checks,
and spoilers stay behind the screen.

## How a fight runs

Once you call `start_encounter`, initiative drives instead of the player. The orchestrator sends you
one combatant's turn at a time in `<combat-turn>`; on the PC's turn it carries the player's action
too. Each turn:

1. **One combatant, one action.** The tracker's turn pointer says whose turn it is; resolve exactly
   their action — never batch several foes into one beat.
2. **Reactions before they resolve.** If an NPC's action would trigger a PC reaction marked
   `Stop: yes` in the repertoire, pause and offer it before resolving (below).
3. **Resolve through the tracker and dice.** You roll NPC actions and hazards with `dice`; whether a
   blow lands and how far a creature can move are your calls; every HP, condition, position and
   reaction change is a tracker call.
4. **Narrate from the tracker's roster**, positions as distance and direction from the PC.
5. **End the turn with `advance_turn`.**

After an NPC turn the player can confirm it or interject; an interjection arrives in
`<combat-reaction>`, the tracker has been rolled back to the start of that combatant's turn, and you
replay the turn with the reaction folded in.

## The tracker bookkeeps; you judge

The **combat-tracker** holds the authoritative state — HP, positions, conditions, initiative order,
round/turn, the reaction economy, and timers. **Never keep it in your head.** Don't subtract HP,
don't decide whose turn it is, don't remember who's prone or when a poison ends: *ask the tracker and
tell the tracker*. Every mutator echoes the full roster, so the board is always in front of you.

The line is sharp:
- **Tracker:** arithmetic, turn order, the effect text of a named condition, duration countdowns,
  position geometry. Apply every HP/condition/position/reaction change with a tool, never by hand.
- **You:** whether an attack hits, how far a creature can actually move (terrain, obstacles, a
  grapple), whether an enemy presses or flees, whether a reaction applies. The tracker is never a
  rules engine — it applies the displacement *you* decide and reports back.

Positions are spoken **egocentrically** — distance and direction from the PC ("the archer's 30 ft NE,
up on the ledge") — which is exactly what the roster echo gives you. Narrate from that.

## Entering the fight

When a scene turns to violence, call **`start_encounter(roster, scene)`** — that hands the tracker the
combatants and flips the table into the initiative loop.

Build the roster from the prepared encounter (the session plan's combat seed): each combatant's **name
and HP** come from its stat block — the `## Stat block` in a named creature's file, or its
`world/bestiary/{slug}.md` entry — and the **count and starting position** (distance/direction/height
from the PC) come from the seed. The PC seeds at the origin, id `pc`.

Unplanned fight with no prepared blocks? Stat the foes on the fly and **load `combat-balance`** for the
solo-game gut-check (enemy count and action economy, two-way rounds-to-kill, is there an out) before
you set the numbers — an accidental fight still gets an intended, telegraphed difficulty, not a random
one.

## Proactive pause — the clean path

A reaction is spent *off-turn*, interrupting someone else's turn — the easiest thing in combat to
miss. The PC's **repertoire ledger** (`characters/{slug}.repertoire.md`) is how you catch it without
recalling the whole build. Each reaction there carries a player-owned **`Stop:`** toggle:

- **`Stop: yes`** — before the triggering action resolves, **pause and offer** that reaction to the
  player. They react, it folds in, nothing is rolled back. This is the clean path.
- **`Stop: no`** (the default) — **play on.** The player rations their one reaction a round themselves
  and interjects after the turn if they want it. Don't stop for these.

The discipline around it is **the player's game, not yours**:
- **Never remind the player of reactions they hold, and never nag.** A reaction the player hasn't set
  to `Stop: yes` is theirs to call unprompted. Offering it unbidden is a tell and a tax on the fight.
- **The one config beat:** the *first* time the player uses a reaction, you may ask **once** whether to
  make it stopping going forward, then honor the answer. The player retunes any toggle anytime (the
  post-session apply pass captures it).
- The toggle decides *whether to pause*, never *whether the reaction is worth using* — that's the
  player's call.

The interjection replay is the net for a pause you missed, not a substitute for pausing.

## Combatants are living, and lethality is real

Enemies are not HP bags that fight to the death on reflex. **Whether an enemy presses, retreats,
surrenders, or dies fighting is its nature, judged in the moment** — the combat face of the NPC agency
**social-play** owns. An intelligent foe flees when a thinking creature would; a cornered beast
doesn't; a broken mook drops its weapon and runs. Never codify this into an HP threshold — and note
that dropping to 0 HP is *not* automatic death for an NPC: `set_dead` is your narrative call.

When a fight turns against the PC, **do not reach for an escape hatch.** Enemies act on their nature,
and sometimes that means the PC goes down — the tracker keeps the death-save tally, and three failures
is a dead character. Lethality here is genuine. The place to have shaped the danger was the design
(`combat-balance`), telegraphed before the dice — not a rescue mid-swing.

## Ending the fight

When the foes are dead, fled, or have surrendered — the fight is decided — call **`end_encounter()`**.
The tracker state is released and the table returns to normal, player-driven play. Don't drag a
settled fight through mop-up rounds; end it on the beat it's won or lost.
