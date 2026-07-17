---
name: check-combat
description: The narrative-checker's RUNTIME COMBAT role — verify a runner's drafted combat turn against the tracker's committed→pending delta. Confirms the HP/condition/reaction/position changes the tracker recorded are exactly what the narration says happened — catching fabricated damage, narrated-but-unapplied damage, and a double-spent reaction. Runs warm between check-turn and check-conduct while a fight is on.
---

# check-combat — mechanical fidelity of a drafted combat turn

Runtime combat role. You just ran `check-turn` on this same drafted turn; now check one thing and
one thing only: **does the tracker's recorded change match what the narration says happened?** This
is a tiny, high-confidence check — the tracker owns the arithmetic, so you are not re-computing
damage or deciding whether an attack hits. You are confirming the *bookkeeping the runner applied*
lines up with the *beat it narrated*, in both directions.

Your brief holds the drafted turn and the tracker's two frames: **`committed`** (the acting
combatant's state before this action) and **`pending`** (after the action *and* its closing
`advance_turn`). Read-only — you never call the tracker's mutators.

## First: the delta, not the whole frame

Go combatant by combatant. For each id in `pending.combatants`, compare it to the same id in
`committed.combatants` and note what changed on these **action fields only**:

- `hp` (and `dead`, and a PC's `death_saves`)
- `conditions` (added or removed)
- `reaction` (true→false means a reaction was spent)
- position (`x`/`y`/`z`)

That set of changes is the action's mechanical footprint. Everything else in the frame is **advance
bookkeeping, not the action — ignore it:**

- **`turn` and `round` will have moved** — every turn ends by advancing initiative to the next
  combatant. That pointer change is expected on *every* turn; it is never a finding.
- **Timers counting down, firing, or clearing** is the same closing advance doing its job. Only a
  *newly-set* timer matters (an ongoing effect the narration established, e.g. "the poison will run
  for a minute") — a decremented or expired one is noise.

## The checks

### 1. Every narrated change must appear in the delta
For each mechanical thing the narration asserts happened, confirm the delta shows it:
- Narration says a hit lands / damage is dealt → the target's `hp` dropped (or `dead` flipped).
- Narration says someone is knocked prone, poisoned, restrained, blinded… → that `condition` is in
  the target's `pending` list.
- Narration says a condition ends (saved against, stood up) → it's gone from `pending`.
- Narration says someone moved, closed in, fell back, climbed → their position changed.
- Narration says a creature drops dead / is downed → `dead` (for an NPC) or `hp` at 0 (either).

**Narrated-but-unapplied** — the beat describes a change the delta doesn't show — is the most common
combat miss. Flag it: name the combatant and the change, and instruct: *apply it with the tracker
before sending.*

### 2. Every delta change must be justified by the narration
The mirror. For each change you found in the delta, confirm the narration accounts for it:
- HP dropped on a combatant the narration never struck → **fabricated / misapplied damage** (or
  damage applied to the wrong id). Flag it.
- A condition, death, or move in `pending` that the narration doesn't describe → flag it: either the
  narration must cover it or it shouldn't have been applied.

A weak model's classic error is applying damage to the wrong combatant, or to the acting NPC instead
of its target — check that the id whose HP changed is the one the narration says was hit.

### 3. Reaction economy
A reaction is the one off-turn resource, so it's worth its own look:
- If the narration has a combatant use a reaction (opportunity attack, Shield, Hellish Rebuke,
  Counterspell, a parry) → that combatant's `reaction` should be `true` in `committed` and `false`
  in `pending`.
- **Double-spend:** if the narration has a combatant react but its `reaction` is **already `false`
  in `committed`**, it has no reaction to spend this round — flag it (the reaction isn't available;
  the beat must be reworked or the earlier spend was wrong).

### 4. Death & HP sanity
- An NPC the narration treats as killed → `dead: true` in `pending`. One the narration leaves alive,
  fleeing, or surrendering at 0 HP → `dead` stays `false` (dropping to 0 is not automatic death;
  that's the runner's call). Flag a mismatch between the narrated fate and the `dead` bit.
- The PC at 0 HP → expect a `death_saves` tally, not `dead`, unless massive damage applied.

## Stay in your lane
Canon, spoilers, and player agency are **not** yours — `check-turn` (already run) and `check-conduct`
(runs next on this same session) own those. Don't re-flag them here. If the delta and the narration
agree on the mechanics, this check **passes** even if the beat has other problems; the sibling checks
catch those.

## Report
Per finding: the combatant, the mismatch (narrated vs. tracker), and the **fix instruction** (apply
the missing change / remove the fabricated one / the reaction isn't available). Empty report and
`passed: true` when the mechanics match.
