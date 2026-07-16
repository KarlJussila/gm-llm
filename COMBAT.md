# COMBAT — combat as a runner play-mode

The design doc for the combat workstream. `SPEC.md` describes what the system *is*; `PLAN.md`
carries packaging/Windows; `BENCHMARK.md` carries the benchmark; this carries combat. **Pre-
implementation** — captured from design discussion, nothing here is built yet.

## Goal

Give `dm-runner` a real combat mode. Combat is the runner's biggest missing capability and a
prerequisite for realistic higher-tier benchmark scenarios. It is rules-dense, stateful, and
sometimes unplanned — exactly what the modest target model (mimo, temp 0.3) is worst at. The design
answers that with the same move the rest of the system already makes: **turn the bookkeeping into a
data structure so it is correct by construction, and leave the model to do only what a model is good
at — narration, spatial/rules reasoning, and treating combatants as living entities.**

## The load-bearing principle

Spoiler discipline was not solved by telling the model "be careful what the PC knows" — it was made
a *data structure* (the knowledge ledger) so the boundary is enforced, not remembered. Combat gets
the same treatment: **a tool-backed tracker holds the authoritative combat state (HP, positions,
conditions, initiative, resources, timers), and the model narrates downstream of it.** The model
never subtracts HP, never decides whose turn it is, never remembers who is prone or what round a
poison expires — it *asks the tracker* and *tells the tracker*. Get this right and most of combat's
difficulty stops being a model problem.

The boundary is sharp and worth stating up front: **the tracker owns deterministic bookkeeping; the
model owns judgment.** Arithmetic, turn order, condition effect-text, duration countdowns, position
geometry → tracker. Whether an attack hits, how far a creature can actually move, whether an enemy
retreats, whether a reaction applies → model. The tracker is never a rules engine.

## Principles (settled in design discussion)

1. **State is authoritative in a tracker, not in the model's head.** A stateful, file-backed opencode
   plugin (the pattern is `plugin/dice-roller.ts`, but persistent) owns HP, conditions, initiative
   order, round/turn position, the reaction/action economy, timers, and position. File-backed (not
   in-memory) because the orchestrator does reverts, resumes, and correction passes; in-memory plugin
   state would desync — and a file the orchestrator can also read is inspectable and preload-able.

2. **Positioning is egocentric, and movement *reasoning* stays with the model.** No grid exposed to
   the model (SPEC is text-only/no-VTT), no pairwise zones. Each combatant carries three fields
   against the PC as origin: **distance** (always; an approximate *number* of feet — fudge the input,
   keep the representation crisp so range checks are deterministic), **height** (only when someone
   climbs/flies), **direction** (coarse bearing, only with more than one opponent). This is O(n)
   state, not O(n²), and position doubles as target disambiguation ("the one on the ledge" → the
   combatant with `height` set). *Whether and how far* anything moves is the model's call — difficult
   terrain, obstacles, grapples/restraints, fly/swim/climb speeds are beyond the orchestrator. The
   tracker only ever applies a displacement the model has already decided and reports the result back.
   - **PC movement is a geometric fan-out.** The PC moving is the one action that shifts *everyone's*
     relative distance. The model decides the PC ends up "20 ft NE"; the tracker translates the whole
     egocentric frame and echoes the re-synced roster, so the model's spatial picture can't drift.
     Backend uses Chebyshev distance (5e's "every square is 5 ft" — diagonals untaxed), keeping the
     vector math round-integer; the model never sees the grid, only "the boss is now 10 ft E of you."
   - Enemy-to-enemy distance — needed only for ally-targeting stat-block mechanics — is *derived*
     approximately from two egocentric vectors (`between`), which is why direction matters once there
     is more than one foe.

3. **The mode-switch is orchestrator-owned and initiative-driven.** Out of combat the *player* drives
   (each message → one DM response). In combat, *initiative* drives: the orchestrator pumps the loop,
   soliciting the player on the PC's turn and narrating one combatant per NPC turn. The model
   *signals* entry/exit (`start_encounter` / `end_encounter`, observed off `reply.tools` like
   `task_complete`), and the orchestrator flips `_in_combat`, which selects the driver, the per-turn
   brief, and the gate. This is the deep version of the mode-switch — not a different reminder, a
   different *loop*.

4. **Reactions: the runner owns the pauses, from a documented repertoire — the tracker does not
   adjudicate eligibility.** Auto-firing a pause on a distance threshold is a false-positive/negative
   machine (weapon in hand? reach 10 not 5? monk? Sentinel *halts* the move so the threshold shouldn't
   cross? open-ended held actions?). Eligibility is PC-build-specific and effectively unbounded, so the
   model owns recognizing pauses — but *not* from its weights. It consults a **reaction/tactical
   repertoire ledger**: a distilled, combat-facing, PC-specific file of `WHEN <trigger> THEN offer
   <reaction>` entries, seeded from the sheet where mechanics are explicit and grown from demonstrated
   play. This is the **third ledger** (knowledge = *what the PC knows*; repertoire = *how the PC
   fights*): distilled from play, PC-specific, consulted by the runner, verified by the checker,
   updated post-session.

5. **Commit is deferred and granular; retcon is full-rollback + partial *replay*, never partial state
   surgery.** The tracker keeps `committed` (hardened truth) and `pending` (the action in flight). A
   per-combatant **confirm gate** follows each NPC action: bare-Enter confirm → commit that
   combatant's delta and advance; interject → treat as a reaction, roll `pending` back to `committed`,
   replay that one combatant's turn with the reaction inserted, commit. So `pending` is only ever *one
   combatant deep*. Pre-interrupt beats survive not by keeping their state but by the DM re-applying
   their *known* results on replay (the 6 damage the player already saw is re-asserted, not re-rolled);
   the kept/redone partition lives in narration, which is regenerated anyway. This is also *more
   correct* than surgical undo for cascades (a halted-and-killed enemy's later action simply is not
   replayed). The mutation vocabulary is **forward mutators + one `rollback`**; commit is
   orchestrator-owned, not a tool.

6. **The combat check validates the `committed → pending` transition.** `check-combat` (a new
   narrative-checker role, warm-chained before `check-conduct` when `_in_combat`) reads *both* blobs:
   `committed` is the known-good baseline that makes the delta checkable — it confirms the HP/position/
   condition changes in `pending` are exactly what the narrated action should produce (catching both
   fabricated damage and narrated-but-unapplied damage, and double-spent economy), plus the usual
   canon/spoiler/agency checks. **Read** access only (via preload of the state file) — never the
   mutators. Per-combatant granularity makes this a tiny, high-confidence check.

7. **Proactive pause is the clean path; the confirm gate and retcon are the safety net.** When the
   runner correctly pauses from the repertoire ledger, the player reacts before the action resolves and
   nothing is rolled back. The confirm gate exists so a *missed* pause stays cheap and recoverable — it
   is not a license to bulldoze. `combat-run` must make that discipline explicit.

8. **Combatants are living entities; the tracker surfaces mechanics, never morale — and PC death is a
   real stake.** The tracker surfaces *mechanical* obligations (saves due, timers firing) but never
   morale. Whether an enemy retreats, presses, surrenders, or fights to the death is **NPC nature
   judged in the moment — the combat face of the NPC agency `social-play` already owns**; an
   intelligent enemy flees when a thinking creature would, a cornered beast doesn't. This must not be
   codified into a threshold. And the runner never reaches for an escape hatch when a fight turns
   against the PC: enemies act on their nature, and sometimes that means the PC dies. Lethality is
   genuine.

## The pieces (mapped to existing seams)

- **Combat tracker** — new `plugin/combat-tracker.ts` + its state file under `.opencode/.orchestrator/`.
  Dumb-but-authoritative; full state, tools, and obligation channel detailed in the next section.
- **Mode-switch plumbing** — `orchestrator/loop.py` gains `_in_combat` and an initiative-driven loop
  surface distinct from `turn(player_input)`: roughly `combat_step()` (advance one combatant; returns
  "awaiting PC input" or "NPC acted, awaiting confirm" + the gated narration), `combat_confirm()`,
  `combat_interject(text)`, `combat_player_action(input)`. Commit/rollback bracketing lives here.
- **`combat-reminder`** — `orchestrator/prompts/combat-reminder.md`, injected in combat's place of
  `turn-reminder`: the strict per-combatant algorithm (whose turn → declare/resolve via tracker+dice →
  narrate → confirm/advance), the proactive-pause discipline, the repertoire-ledger consult.
- **`combat-run` skill** — `assets/opencode/skills/combat-run/SKILL.md` (the reserved `*-run` play-mode
  slot SPEC already names). Loaded on entry; `session-run`'s universal craft still holds.
- **`check-combat` skill** — `assets/opencode/skills/check-combat/SKILL.md`, wired into `gate.check()`
  under `_in_combat`. Validates the transition against the preloaded tracker state.
- **`combat-balance` skill** — `assets/opencode/skills/combat-balance/SKILL.md`. DM-facing at planning,
  runner-loadable for unplanned combat. Craft prose (see Balance), not a mechanism.
- **Reaction/tactical repertoire ledger** — a new canon file kind (template under
  `canon-conventions/templates/`), one per PC. Seeded at character-create/level-up from the sheet;
  grown post-session by the reconcile pipeline (`log-extract`/`apply-*`) capturing showcased reactions.
- **Planning: stat blocks + encounter prep** — a stat-block template (recurring/named creatures →
  canon entity files with a stat-block section, registered in `INDEX.md`; generic mooks →
  session-plan-scoped), consumed by `start_encounter`. `encounter-plan` keeps its "situations, not stat
  blocks" stance and gains the stat-block/prep layer alongside it.

## Tracker — state, tools, and the obligation channel

**Tool surface — few, single-purpose, simple-argued, and enum-free** (per-call clarity beats raw
call-count for a weak model; most turns use only 2–3). opencode has no enum type, so any `"a"|"b"` arg
is just a hand-validated string a modest model fumbles — prefer booleans or separate verbs, with
lenient normalization only for the one irreducible vocab (`direction`, e.g. `ne`/`NE`/`northeast`):

```
start_encounter(roster, scene)                 end_encounter()
damage(id, amount)   heal(id, amount)
add_condition(id, name)   remove_condition(id, name)
move(id, {distance?, height?, direction?})     # NPC, set-absolute
pc_move(distance, direction)                   # PC displacement; returns re-synced roster
remind_in(rounds, note) -> id                  remind_each_turn(combatant, note, {owner?}) -> id
clear_timer(id)
spare(id)   flee(id)   death_save(id, success)  # other down-states derived from HP + death saves
advance_turn()   rollback()
reads:  state()   ·   in_range(id, feet) -> bool   ·   between(a, b) -> ~feet
```

Every mutator echoes the **full compact roster with ids**, so the current id list, positions, and HP
are always in front of the model — the echo after `pc_move` *is* the position report-back.

**Identity/addressing.** `start_encounter` assigns stable ids from the roster (`goblin` ×3 →
`goblin-1..3`). The `turn` field disambiguates by default; position disambiguates by reference ("the
one on the ledge"). The roster echo keeps ids current so the model mutates the right combatant.

**Conditions are a bounded standard library, not free tags.** The model calls
`add_condition(goblin-2, prone)` (minimal input); the tracker owns the canonical effect text and
duration for D&D's ~15 named conditions and echoes them back (rich, self-documenting output — the
ledger move: don't make the model recall what prone does, hand it the rule). Save-ends conditions are
just a `remind_each_turn` on the target.

**Per-turn economy — tracked, gate-enforced.** Action / bonus / reaction / `movement_remaining`, reset
on `advance_turn` (reaction refreshes at the combatant's own turn). Informational for the common
one-attack turn; `check-combat` catches a double-action against it rather than demanding perfect
spend-discipline from the model.

**Death/downed is a code-owned mini-state.** At 0 HP the tracker sets the state itself — `dead` for an
NPC, `unconscious` + a death-save tally (3/3) for the PC — plus the massive-damage instant-death check.
The model only signals the two choices code can't infer: `spare(id)` (drop non-lethal instead of
killing) and `flee(id)` (leaves the fight); death saves report as a boolean, `death_save(id, success)`.
No status enum.

**The obligation channel.** Save-ends conditions, effect timers, and any "at the start/end of X's turn,
do Y" are trigger-hung reminders the tracker surfaces at the matching turn boundary on `advance_turn`.
Two primitives cover every shape — they never mix, and the rare compound composes (a `remind_in` whose
note tells the model to set a `remind_each_turn`):

```
remind_in(rounds, note) -> id                       # fires ONCE, `rounds` out: delayed effects, plain expiries
remind_each_turn(combatant, note, {owner?}) -> id   # fires EVERY that-combatant's-turn: save-ends, per-round effects
```

- The trigger (which combatant's turn, or how many rounds out) says *when it fires*; the note says
  *what to remember* — the affected combatant lives in the note, since the triggering combatant often
  isn't the affected one (the caster's turn moves the sphere; the *target's* turn ends the hold).
- **Intra-turn timing lives in the note too.** Save-at-*end* vs. tick-at-*start* is not a structured
  arg (an enum code never branches on): the tracker fires a combatant's reminders when its turn comes
  up, and the model resolves each at the right beat, cued by the note.
- **No duration parameter.** Fixed-duration effects ("1 minute" = 10 rounds) put the length in the
  note; the tracker surfaces **elapsed rounds** on each recurring fire, and the model ends it by
  comparison — the counting (what weak models drop) is offloaded, the compare (trivial) is the model's.
- **Every timer gets an auto-assigned id, echoed when it fires**, so the model can `clear_timer(id)`
  the right one without ambiguity. One-shot `remind_in` auto-clears after firing.
- **Culling is the model's judgment**, because "which death ends which effect" is rules knowledge we
  keep out of the tracker: the tracker fires the reminder, the model sees the dead combatant in the
  echoed roster and dismisses/clears a stale one. The one cheap concession — an optional **`owner`**
  id the tracker auto-culls on that combatant's death — is a plain foreign-key cleanup (tag the caster
  as owner → concentration-ends-on-death for free), not a rules engine.

**Tracker state (sketch — serialization not locked):**

```jsonc
{
  "encounter": "goblin-ambush", "round": 2, "turn": "goblin-2",
  "committed": {                                   // hardened truth as of the last confirmed action
    "combatants": {
      "pc":       { "hp": 24, "hp_max": 31, "status": "alive", "conditions": [],
                    "economy": { "action": true, "bonus": true, "reaction": true, "move_ft": 30 } },
      "goblin-2": { "hp": 5, "hp_max": 12, "status": "alive",
                    "conditions": [{ "name": "prone", "effect": "...", "ends": null }],
                    "distance": 30, "height": 0, "direction": "NE" }    // egocentric, vs. the PC
    },
    "initiative": ["pc", "goblin-1", "goblin-2"],
    "timers": [{ "id": 3, "kind": "each_turn", "combatant": "goblin-boss", "owner": "goblin-boss",
                 "note": "move flaming sphere (10 rds)", "set_round": 1 },
               { "id": 4, "kind": "in", "fires_round": 5, "note": "bless ends" }]  // elapsed = round − set_round, surfaced on fire
  },
  "pending": { /* same shape: committed + the one action in flight; == committed after a commit */ }
}
```

## The combat loop

```
enter combat (runner calls start_encounter; orchestrator flips _in_combat)
loop over initiative (tracker owns the order and the position):
  advance_turn → tracker fires any matching saves/timers (with their ids) as obligations
  PC's turn:   solicit full player input → DM adjudicates via tracker+dice → gate → commit
  NPC's turn:  DM narrates ONE combatant's action → gate (committed→pending) → present + confirm gate
                 confirm (Enter) → commit that delta, advance
                 interject      → reaction: rollback pending→committed, replay this combatant's turn
                                  with the reaction, gate, commit, advance
until the tracker says the fight is over (all foes down/fled) or the runner calls end_encounter
```

Player turns are symmetric to NPC turns for commit purposes — a DM error on the PC's own turn is
equally retconnable within its window. The wrap/`session-length` machinery should not interrupt a
fight mid-round (detail TBD).

## Balance — a skill, not a mechanism

Not a tracker feature and not XP math. **`combat-balance`** is craft prose: DM-facing at planning,
runner-loadable for unplanned combat.

**Why CR is the wrong tool here: this is a single-PC system.** CR and the encounter-budget system are
calibrated for a ~4-PC party. A lone PC against a group is action-economy hell — it eats N attacks per
round and deals one character's worth back — and that, not any creature's CR, is the dominant variable.
That is *why* by-feel beats the math for a solo game: the DM's feel tracks action economy and burst,
which CR budgets smear away by assuming four bodies. So the skill doesn't teach CR better; it makes the
levers a feel-DM actually uses explicit for a model that has none:

1. **Action economy first.** For a solo PC, enemy *count* dominates individual power — three same-tier
   minions is dangerous; one big creature is often *safer* than several small ones of equal budget,
   because the PC's own economy competes evenly against one.
2. **Two-way rounds-to-kill.** Roughly how many rounds for the enemies to drop the PC vs. for the PC to
   clear the enemies' total HP. First ≤ second and no out → the PC probably goes down.
3. **Burst and save-or-die swing.** Can enemies focus-fire to spike the PC in one round? A single
   failed save vs. a control/incapacitate effect is far swingier than HP loss.
4. **The PC's outs and resource state.** A "deadly" fight with an escape route or a fresh PC is
   survivable; a "moderate" one in a sealed room against a depleted PC isn't. Difficulty is contextual.
5. **Shape difficulty with design levers, not a target number:** enemy count, HP/damage, starting
   distance, terrain, reinforcement timing, and the *objective* (kill-them-all vs. survive-three-rounds
   vs. reach-the-door).

Split like the rest of the system: a **heavier planning face** (the DM shaping an encounter to an
intended feel, quantifying rounds-to-kill) and a **lighter runtime gut-check** for unplanned combat
(*count the enemies and their action economy; can they drop you faster than you can drop them; is there
an out?* — and if it's lethal, that's allowed, just intentional and telegraphed, not accidental). The
"escape valve" idea survives only reframed: **design-time levers + emergent NPC behavior**, never a
PC-rescue reflex (principle 8).

## Open decisions

- **Tracker serialization + HP roll-vs-average** on instantiation (fixed average is one fewer roll;
  rolled gives variance). The `state()`/mutator echo format.
- **AoE query.** "Everyone within 20 ft of that point" is derivable from the egocentric geometry and
  worth a later `aoe(center, radius)` read; deferred from C0 to avoid schema bloat.
- **Reaching back past a confirmed combatant.** By design, confirming combatant A closes A's reaction
  window, so a reaction referencing an already-committed combatant is handled going forward, not
  retconned. Confirm-as-consent is what makes granular commit sound; flagged as a deliberate scope
  boundary, not a gap.

## Roadmap (design-stage; phases ordered so each is useful alone)

The mechanical spine is **deterministic and unit-testable without the benchmark**; the narrative craft
is what the benchmark later tunes. Build and verify the spine on its own terms; treat `combat-run`
prose and `combat-balance` as what B3's baseline (see `BENCHMARK.md`) refines. This resolves the
chicken-and-egg where combat is a prerequisite for realistic higher-tier scenarios but the benchmark is
what would validate its prompts.

### C0 — Tracker plugin + schema *(code only, unit-tested)*
The `combat-tracker` plugin and state file: combatants, egocentric position, the bounded condition
library (tag-in, effect+duration-out), per-turn economy, death/downed mini-state, initiative, the
timer/obligation channel (`remind_in` + `remind_each_turn`, auto-ids echoed on fire, elapsed-round
surfacing, owner-cull), `committed`/`pending`, forward
mutators, `pc_move` fan-out (Chebyshev), `rollback`, range/`between` reads,
`start_encounter`/`end_encounter`. Verified by direct plugin tests — no model in the loop. *Exit: the
tracker is provably correct as a state machine.*

### C1 — Mode-switch plumbing in `loop.py` *(code only)*
`_in_combat`, the initiative-driven loop surface, orchestrator-owned commit/rollback bracketing,
`start`/`end` signal observation off `reply.tools`. Verified under the mock backend. *Exit: a scripted
combat drives through the loop with correct commit/rollback boundaries and no model.*

### C2 — Gate: `check-combat`
The role skill + `gate.check()` branch + state-file preload into the check brief. *Exit: a drafted
combat action is validated against the `committed → pending` transition.*

### C3 — Repertoire ledger
Template + seed at character-create/level-up + reconcile capture of showcased reactions. *Exit: a PC
accrues a combat-facing reaction repertoire the runner and checker read.*

### C4 — Planning: stat blocks, encounter prep, `combat-balance`
Stat-block template, `encounter-plan` extension (design levers + objective, not PC-rescue rails),
`start_encounter` instantiation from prepared blocks, and the `combat-balance` skill (planning face +
runtime gut-check). *Exit: a planned encounter arrives at the table as loadable combatants at an
intended, un-fudged difficulty.*

### C5 — `combat-run` + `combat-reminder` craft *(prose; benchmark-tuned)*
The play-craft: the per-combatant algorithm, proactive-pause discipline, repertoire consult, the
confirm/retcon contract, NPC-nature morale, real lethality. Tuned against the benchmark once a baseline
exists. *Exit: a full combat runs end-to-end at the table.*
