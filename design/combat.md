# Combat — a runner play-mode

Plan of record for combat. What the system is → [README.md](README.md); the benchmark →
[benchmark.md](benchmark.md).

**Status: built and shipped (0.3.0), mock-verified only** — every part of this has been exercised
under the mock backend and the `dev/` suites, and none of it has ever run against a live model.
The shakedown is `ROADMAP.md` track **luna**. The Luna rebuild keeps this design and changes two
things — no per-step reminder, and the fidelity check moves after play
([luna.md](luna.md) § Combat). This doc describes the design and where it lives in the tree.

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

## Principles

1. **State is authoritative in a tracker, not in the model's head.** A stateful, file-backed opencode
   plugin (the pattern is `plugin/dice-roller.ts`, but persistent) owns HP, conditions, initiative
   order, round/turn position, the reaction economy, timers, and position. File-backed (not
   in-memory) because the orchestrator does reverts, resumes, and correction passes; in-memory plugin
   state would desync — and a file the orchestrator can also read is inspectable and preload-able.

2. **Positioning is egocentric, and movement *reasoning* stays with the model.** No grid exposed to
   the model (text-only, no VTT — [README.md](README.md) § Constraints), no pairwise zones. **The model-facing frame is egocentric —
   every position is spoken as distance/height/direction against the PC as origin** — but *storage is
   world-absolute Cartesian* (each combatant an `x/y/z` in feet, the PC seeded at the origin), and the
   egocentric view is a *projection* rendered on demand. This is the load-bearing split: Cartesian is
   exact and never accumulates rounding, while the model only ever sees "the boss is 10 ft E of you."
   Each projection carries **distance** (always; the model fudges the input, the stored coord stays
   crisp), **height** (z, surfaced only when someone climbs/flies), **direction** (coarse bearing,
   snapped to 8 points, meaningful with more than one opponent). This is O(n) state, not O(n²), and
   position doubles as target disambiguation ("the one on the ledge" → the combatant with a height).
   *Whether and how far* anything moves is the model's call — difficult terrain, obstacles, grapples/
   restraints, fly/swim/climb speeds are beyond the orchestrator. The tracker only ever applies a
   displacement the model has already decided and reports the result back.
   - **PC movement is a pure origin shift.** There is one `move` tool; calling it on the PC is the one
     case that shifts *everyone's* relative distance — but with Cartesian storage it's just moving the
     PC's own point, so every other combatant's *displayed* position re-syncs for free (no fan-out
     loop, no per-combatant re-rounding). The model decides the PC ends up "20 ft NE"; the tracker
     translates that one displacement and echoes the re-synced roster, so the model's spatial picture
     can't drift. Backend uses Chebyshev distance (5e's "every square is 5 ft" — diagonals untaxed),
     keeping the projected feet round-integer; the model never sees the grid.
   - Enemy-to-enemy distance — needed only for ally-targeting stat-block mechanics — is now *exact*
     Chebyshev between two stored points (`distance_between`), no longer a lossy re-derivation from two
     projected vectors; direction still matters for how the model narrates and disambiguates foes.

3. **The mode-switch is orchestrator-owned and initiative-driven.** Out of combat the *player* drives
   (each message → one DM response). In combat, *initiative* drives: the orchestrator pumps the loop,
   soliciting the player on the PC's turn and narrating one combatant per NPC turn. The model
   *signals* entry/exit (`start_encounter` / `end_encounter`, observed off `reply.tools` like
   `task_complete`), and the orchestrator flips `_in_combat`, which selects the driver, the per-turn
   brief, and the gate. This is the deep version of the mode-switch — not a different reminder, a
   different *loop*.

4. **Reactions: the runner owns the pauses, from a documented repertoire — the tracker does not
   adjudicate eligibility.** Auto-firing a pause on a distance threshold is a false-positive/negative
   machine (weapon in hand? reach 10 not 5? monk? a movement-halting feat that *stops* the move so the
   threshold shouldn't cross? open-ended held actions?). Eligibility is PC-build-specific and effectively unbounded, so the
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
   fabricated damage and narrated-but-unapplied damage, and a double-spent reaction), plus the usual
   canon/spoiler/agency checks. **Read** access only (via preload of the state file) — never the
   mutators. Per-combatant granularity makes this a tiny, high-confidence check.

7. **Proactive pause is the clean path; the confirm gate and retcon are the safety net.** When the
   runner correctly pauses from the repertoire ledger, the player reacts before the action resolves and
   nothing is rolled back. The confirm gate exists so a *missed* pause stays cheap and recoverable — it
   is not a license to bulldoze. `combat-run` must make that discipline explicit.
   - **Which reactions stop is the *player's* choice, not a runner heuristic — a per-reaction `Stop:
     yes/no` toggle in the repertoire.** Whether pausing for a given reaction is worth the
     interruption is a taste call only the player can make: a broad, fires-every-turn trigger (Shield
     on any hit; Hellish Rebuke on any hit that damages the PC) is exactly the kind most players would
     rather call themselves than have the fight stop for several times a round — but that's *their*
     call, and a player who wants it surfaced can set it.
     So each reaction carries a **player-owned toggle**: `Stop: yes` → the runner proactively offers;
     `Stop: no` → the runner plays on and the player interjects at the confirm gate (self-rationing
     their one reaction/round). **New reactions default `Stop: no`, and the runner never reminds the
     player of reactions they hold** — that's the player's game to play. The one config beat: the first
     time a reaction is used, the runner may ask *once* whether to make it stopping going forward, and
     the player can retune any toggle anytime (captured post-session by the apply pass). `combat-reminder`
     reads the toggle; it never judges breadth itself, and never nags.

8. **Combatants are living entities; the tracker surfaces mechanics, never morale — and PC death is a
   real stake.** The tracker surfaces *mechanical* obligations (saves due, timers firing) but never
   morale. Whether an enemy retreats, presses, surrenders, or fights to the death is **NPC nature
   judged in the moment — the combat face of the NPC agency `social-play` already owns**; an
   intelligent enemy flees when a thinking creature would, a cornered beast doesn't. This must not be
   codified into a threshold. And the runner never reaches for an escape hatch when a fight turns
   against the PC: enemies act on their nature, and sometimes that means the PC dies. Lethality is
   genuine.

## The pieces (mapped to existing seams)

- **Combat tracker** — new `plugin/combat-tracker.ts` (thin file-backed adapter, the only export is the
  plugin) over a pure engine in `plugin/combat/engine.ts` + its state file under `.opencode/.orchestrator/`.
  The engine lives one directory down because opencode auto-loads every direct child of `plugin/` as a
  plugin (`Glob.scan("{plugin,plugins}/*.{ts,js}")`) — so the unit-tested engine functions can be freely
  exported without the loader mistaking them for plugins. Dumb-but-authoritative; full state, tools, and
  obligation channel detailed in the next section.
- **Mode-switch plumbing** — `orchestrator/loop.py` gains `_in_combat` and an initiative-driven loop
  surface distinct from `turn(player_input)`: roughly `combat_step()` (advance one combatant; returns
  "awaiting PC input" or "NPC acted, awaiting confirm" + the gated narration), `combat_confirm()`,
  `combat_interject(text)`, `combat_player_action(input)`. Commit/rollback bracketing lives here.
- **`combat-reminder`** — `orchestrator/prompts/combat-reminder.md`, injected in combat's place of
  `turn-reminder`: the strict per-combatant algorithm (whose turn → declare/resolve via tracker+dice →
  narrate → confirm/advance), the proactive-pause discipline, the repertoire-ledger consult.
- **`combat-run` skill** — `assets/opencode/skills/combat-run/SKILL.md` (the reserved `*-run` play-mode
  slot the skill-naming convention reserves).
  Loaded on entry; `session-run`'s universal craft still holds.
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
move(id, {distance?, height?, direction?})     # "pc" fans out to everyone; anyone else is absolute-set
set_dead(id, dead)   death_save(id, success)    # NPC death is a narrative call; PC death is derived
use_reaction(id)
remind_in(rounds, note) -> id                  remind_each_turn(combatant, note, {owner?}) -> id
clear_timer(id)
advance_turn()   rollback()
reads:  state()   ·   describe(id)   ·   distance_between(a, b) -> feet   # Chebyshev over stored coords
```

(No `in_range` tool: every mutator's roster echo already prints each foe's projected distance, so a
range check is a comparison the model reads off the board rather than a round-trip — one fewer tool on
a surface a weak model has to choose from.)

**Area-of-effect is three shape reads, and the tracker does the geometry.** `burst` (a radius effect —
sphere, cylinder, or cube; its LLM-facing description says so), `cone`, and `line` are each an exact
filter over the stored Cartesian coords, returning the caught combatants in egocentric terms. The
model places the aim *in the egocentric frame it already speaks* and never sees a coordinate —
exposing coords would push the geometry back onto the weak model, the exact thing principle 2
offloads. **One input shape per tool, no id-or-point overloading:** `burst`'s center is a placed point
(`distance`/`direction`/`radius`, with `distance 0` = on the PC, so nobody is exempt); `cone` and
`line` emanate from an explicit `origin` combatant id — **any** combatant, whether or not it is their
turn (a readied breath weapon, an off-turn effect, any caster) — and never catch the origin. A
combatant-id origin is a single clean arg, not the overloading we rule out. All three are pure reads:
the model then applies `damage` per hit. Cube and cylinder fold onto `burst`. Built as all three
rather than on demand because this is an open, improvised system where any fight can summon a breath
weapon or a lightning line — a mechanic that *can* arise *will*.

Every mutator echoes the **full compact roster with ids**, so the current id list, positions, and HP
are always in front of the model — the echo after `move("pc", ...)` *is* the position report-back.
`describe(id)` is the single-combatant equivalent for when the compact echo isn't enough — full
condition effect text, reaction state, death saves, position, and any timers pinned to that combatant's
turn, in human-readable prose (the one read that surfaces a live timer between fires).

**Identity/addressing.** `start_encounter` assigns stable ids from the roster (`goblin` ×3 →
`goblin-1..3`). The `turn` field disambiguates by default; position disambiguates by reference ("the
one on the ledge"). The roster echo keeps ids current so the model mutates the right combatant.

**Conditions are a bounded standard library, not free tags.** The model calls
`add_condition(goblin-2, prone)` (minimal input); the tracker owns the canonical effect text for D&D's
~15 named conditions and echoes it back (rich, self-documenting output — the ledger move: don't make
the model recall what prone does, hand it the rule). Duration is never a condition field — save-ends
and fixed-length conditions alike are just a `remind_each_turn`/`remind_in` on the target, per the
obligation channel below.

**Reaction is the one tracked resource, not a full economy.** Action, bonus action, and movement are
once-per-round resources spent *on a combatant's own turn* — the model keeps those straight without
help, the same reasoning that keeps movement distance itself a model judgment call (see principle 2).
A reaction is different: it's spent *off-turn*, interrupting someone else's turn, which is exactly the
eligibility question the confirm-gate/interject flow (principles 4–5) turns on. So each combatant
carries one `reaction` boolean, reset to `true` on that combatant's own `advance_turn` and set `false`
by `use_reaction(id)` — the one piece of economy worth a source of truth for the interject flow and
`check-combat` to read.

**Death is a single boolean, not a status enum.** `dead` is the only status bit a combatant has —
"alive" is simply `!dead`. Ordinary damage reaching 0 HP does **not** auto-kill an NPC: whether a
downed enemy is dead, fleeing, or surrendering is the model's narrative call (principle 8), signaled
with one tool, `set_dead(id, dead)` — boolean in, callable either direction, so a wrong call is
trivially corrected. Fleeing is not a tracked state at all; it's just `move` plus narration, same as
any other movement. The one mechanical exception is 5e's massive-damage rule (overkill ≥ `hp_max`
while already at 0 forces `dead = true` unconditionally, PC included) — genuinely deterministic, so
it's code-owned. The PC additionally gets a `death_saves` tally once at 0 HP, reported via a boolean,
`death_save(id, success)`: three failures sets `dead = true`; three successes just stops the prompting
(still 0 HP, still alive — the roster echo already shows that, no separate label needed).

**The obligation channel.** Save-ends conditions, effect timers, and any "at the start/end of X's turn,
do Y" are trigger-hung reminders, each pinned to a **turn-slot**, not a round-boundary. `advance_turn`
steps through initiative one slot at a time — a dead combatant still occupies their slot (their
initiative is still "passed," just with no action to narrate), so a timer pinned to a dead combatant
still counts down and fires on schedule. `round` only increments when the walk wraps back to the top
of initiative. Two primitives cover every shape — they never mix, and the rare compound composes (a
`remind_in` whose note tells the model to set a `remind_each_turn`):

```
remind_in(rounds, note) -> id                       # fires ONCE, `rounds` occurrences of the calling combatant's slot from now
remind_each_turn(combatant, note, {owner?}) -> id   # fires EVERY time `combatant`'s slot comes up: save-ends, per-round effects
```

- **`remind_in` binds to whoever's turn is active when it's called** — no combatant argument needed.
  "In 3 rounds" means the next 3 times *that* slot comes back around, so a spell cast on the caster's
  turn naturally times out on the caster's own future turn.
- **`remind_each_turn` takes an explicit `combatant`**, since the affected combatant is often not the
  one setting the timer (the caster's turn moves the sphere; the *target's* turn ends the hold) — the
  note carries *what to remember*, the `combatant` arg carries *whose slot fires it*.
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

**Tracker state:**

```jsonc
{
  "encounter": "goblin-ambush", "next_timer_id": 5,   // next_timer_id top-level: never rewinds on a rollback
  "committed": {                                   // hardened truth as of the last confirmed action
    "turn": "goblin-2", "round": 2,                // turn/round live IN the frame, so a swap carries them
    "combatants": {
      "pc":       { "hp": 24, "hp_max": 31, "dead": false, "conditions": [], "reaction": true,
                    "x": 0, "y": 0, "z": 0 },                           // the origin of the egocentric frame
      "goblin-2": { "hp": 5, "hp_max": 12, "dead": false, "reaction": true,
                    "conditions": [{ "name": "prone", "effect": "..." }],
                    "x": 21, "y": 21, "z": 0 }    // world coords; projects to ~30 ft NE of the PC
    },
    "initiative": ["pc", "goblin-1", "goblin-2"],
    "timers": [{ "id": 3, "kind": "each_turn", "combatant": "goblin-boss", "owner": "goblin-boss",
                 "note": "move flaming sphere (10 rds)", "set_round": 1 },
               { "id": 4, "kind": "in", "combatant": "pc", "passes_remaining": 3, "note": "bless ends" }]
  },
  "pending": { /* same shape: committed + the one action in flight; == committed after a commit */ }
}
```

`turn`/`round` sit inside each frame (not top-level) so `commit`/`rollback` snapshot the turn pointer
with everything else — that is what lets each turn end by calling `advance_turn` and still replay
cleanly on an interject (the rollback rewinds the pointer to the interrupted combatant). `next_timer_id`
stays top-level: it must never rewind, or a rolled-back timer's id could be handed out twice.

## The combat loop

```
enter combat (runner calls start_encounter; orchestrator flips _in_combat)
loop over initiative (the tracker's own turn pointer is the cursor):
  whose turn = the pending frame's turn pointer (advanced by the previous turn's closing advance_turn,
               which already fired this combatant's saves/timers as obligations)
  PC's turn:   solicit full player input → DM adjudicates via tracker+dice, ends by advance_turn → gate → commit
  NPC's turn:  DM resolves ONE combatant's action, ends by advance_turn → gate (committed→pending)
                 → present + confirm gate
                 confirm (Enter) → commit that delta
                 interject      → reaction: rollback pending→committed (pointer rewinds to this
                                  combatant), replay the turn with the reaction, gate, present again
until the runner calls end_encounter (all foes dead or narratively withdrawn)
```

Player turns are symmetric to NPC turns for commit purposes — a DM error on the PC's own turn is
equally retconnable within its window. The wrap/`session-length` machinery should not interrupt a
fight mid-round (detail TBD).

**Confirming a combatant closes their reaction window — by design.** A reaction that references an
already-committed combatant is handled going forward, not retconned. Confirm-as-consent is what makes
granular commit sound: if a confirmed beat could still be reopened, `pending` would stop being one
combatant deep and the replay guarantee would go with it. This is a deliberate scope boundary, not a
gap.

**The turn pointer travels in the snapshot, so the advance can end the turn.** `turn`/`round` live
inside the `committed`/`pending` frames, so a `rollback` (committed→pending) restores the turn pointer
along with HP/conditions/timers. That is what lets each combatant's turn *end* by calling `advance_turn`
(seating the next combatant, firing their timers) rather than needing a separate orchestrator-driven
advance step: `committed` holds this combatant's pre-action start, the action mutates `pending` and
advances its pointer, and an interject's `rollback` rewinds `pending` — pointer included — to replay
*this* combatant. Were `turn` top-level and shared, rollback couldn't rewind it and the replay would
resolve the wrong combatant; that constraint (and the extra advance model call it forced) is why the
pointer moved into the frame. A combatant's timers therefore fire on the *previous* turn's closing
advance — one beat early in the transcript, resolved on the turn they belong to (a `combat-reminder`
matter). `next_timer_id` stays top-level so a rolled-back timer id is never reused.

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

## Implementation map

Where the design above lives in the tree, and the calls that are not recoverable from reading the
code. This is not a sequence — ROADMAP owns sequencing, and nothing here is outstanding.

**The tracker** — `plugin/combat-tracker.ts`, a thin file-backed adapter over a pure engine in
`plugin/combat/engine.ts`, state under `.opencode/.orchestrator/`. The engine sits one directory
down because opencode auto-loads every direct child of `plugin/` as a plugin
(`Glob.scan("{plugin,plugins}/*.{ts,js}")`), so the unit-tested engine functions can be exported
freely without the loader mistaking them for plugins.

**The loop** — `gm_llm/orchestrator/combat.py`: a `CombatState` file-wrapper (the two frame swaps —
`commit` = pending→committed, `rollback` = committed→pending, both carrying the in-frame turn
pointer) plus a `CombatMixin` on `Game` exposing `combat_step()`, `combat_confirm()`,
`combat_interject(text)`, `combat_player_action(input)`, and `in_combat`.

- **Every turn ends by advancing (advance-at-end).** The runner resolves its action and calls
  `advance_turn` as its closing act; the orchestrator owns *only* the two frame swaps, never the
  tracker's advance semantics. This is forced as well as preferred — opencode exposes no
  execute-a-tool endpoint, so the orchestrator cannot run the advance itself. One model call per
  combatant, no separate advance step, no first-step special case; a forgotten advance shows up as
  the pointer not moving and is nudged once (`_ensure_advanced`).
- **The PC's turn commits directly** (a player doesn't confirm their own beat); an NPC turn awaits
  confirm; an interject re-presents for confirm, so a reaction to a reaction stays cheap.
- **Resume rolls an uncommitted action back and replays it.** `_in_combat` recovers off the
  persisted tracker file, but an in-flight NPC action awaiting confirm lives only in memory — so a
  crash between drafting and confirming would otherwise skip the confirm gate and lose the
  un-appended narration. A `CombatState.in_flight()` (`committed != pending`) guard at the top of
  `combat_step` rolls back to `committed` and re-resolves the interrupted combatant: the same
  retcon-is-replay move an interject makes, and it covers a PC mid-draft crash identically.

**The gate** — `check-combat` is a narrative-checker role warm-chained **between** `check-turn` and
`check-conduct`, so it inherits the canon/ledger context and stays sequenced in the correction brief.

- **It runs only on the action beats.** `gate.check(narration, player_msg, in_combat)` carries the
  flag; `combat.py` passes `in_combat=True` from `combat_step`/`combat_interject`/
  `combat_player_action` only. The play-driven entry turn and the `end_encounter` exit beat stay
  `False` — the entry seeds `committed == pending` (an empty delta) and the exit's state file is
  already deleted, so neither has a transition to validate.
- **Read-only preload, defensively guarded.** `gate._combat_blobs` reads the two frames as pretty
  JSON into the brief; if the file is absent (the closing beat racing the delete) the check is
  skipped and `GateResult.combat` is `None`. The gate never touches the mutators (principle 6).
- **It validates the delta, not the frame** — diffing `committed → pending` on hp/dead/conditions/
  reaction/position in both directions, catching narrated-but-unapplied and fabricated damage plus
  reaction double-spend, and explicitly ignoring the closing advance's turn-pointer/round/timer
  noise. Canon, spoiler and agency are the sibling checks' business.

**The repertoire ledger** — the PC's fourth file, `characters/{slug}.repertoire.md`, from
`pc-repertoire.template.md`; documented in `canon-conventions` §2 and §3.

- **Seeded at character-create** from the sheet's explicit reactions (opportunity attack always,
  plus any reaction spell or feature the sheet shows), leaving the rest to grow from play.
- **Grown in the *capability* pass, not the state pass.** The repertoire is capability-lineage, so
  it lives with the sheet in **apply-canon**, keeping the whole PC-capability signal in one pass,
  while the *knowledge* ledger stays apply-state's. `log-extract` taxonomy item 13 (*Combat
  reactions & tactics*) captures the WHEN→THEN trigger rather than just an ability name; apply-canon
  reads it in; `check-propagation` audits that it landed.
- `completeness.py` skips the `.repertoire.md` companion — only the sheet carries the Vitals
  contract.

**Planning data** — one stat-block format, two homes, both file-backed.
`stat-block.template.md` (HP·AC·speed / all six abilities as score-check-save / attacks / defenses &
senses / special-incl-reactions / tactics & nature) is the sole format. Named and recurring creatures
carry it as an optional `## Stat block` in their existing NPC file; **generic reusable creature types
get their own stateless bestiary file** — `world/bestiary/{slug}.md`, `type: creature`, registered in
INDEX's `## Bestiary` table and referenced by `[[slug]]`. Every combatant is therefore a
slug-addressed file, so `start_encounter` loads uniformly and a reused creature is not re-authored
per session. (The first sketch inlined mook blocks in the session plan; this replaced it.) The
intrinsic block holds HP; the *encounter seed* supplies count and starting position.

- **The combat `## Stat block` is distinct from the required `## Stats (rough sketch)`**, which stays
  a social/exploration capability gauge. The stat block is optional (combatants only), so
  `completeness.py` leaves it alone, and its heading doesn't prefix-collide with the required
  "Stats". Bestiary files are lint-exempt for free — `type: creature` isn't in `completeness.py`'s
  map and `world/bestiary/` isn't a scanned dir.
- **`encounter-plan` gained a combat layer over its situations stance**, not instead of it: a combat
  seed still leads with situation/lever/complication, and additionally commits combatants, starting
  positions (egocentric — starting distance is a difficulty lever), and the objective, which is not
  always kill-them-all.

**The craft — two homes, mirroring `session-run`/`turn-reminder`.** The durable craft is the
**`combat-run` skill** (loaded on entry, held in the runner session); the terse per-turn algorithm is
**`combat-reminder`** (`gm_llm/orchestrator/prompts/combat-reminder.md`, self-fenced), re-sent in
front of every combat step so it cannot decay. They don't restate each other: the algorithm lives in
the reminder, the judgment (pause discipline, morale, lethality, instantiation) in the skill.

- **The permission blocker, which would have failed at the table.** `dm-runner` is `'*': deny`, so
  plugin tools need an explicit allow — the runner literally could not call the tracker. Its
  allow-list now names the tracker tools, with **`rollback` deliberately excluded**: the
  orchestrator owns the frame swaps and does rollback itself in Python, so the model must never
  rewind state underneath it. This was invisible under the mock backend, which doesn't enforce
  permissions — the standing lesson being that a permission gap is exactly the class of bug mock
  verification cannot see.
- **Entry and exit are wired at both ends.** `dm-runner` has a Combat section (load `combat-run` +
  `start_encounter` to enter, `end_encounter` to leave, orchestrator drives the fenced steps
  between); `session-run`'s companion list and `turn-reminder` name `combat-run` as the fight-entry
  mode.
- A combatant's timers fire on the *previous* turn's closing advance — one beat early in the
  transcript, resolved on the turn they belong to. That is a `combat-reminder` matter, and it is the
  cost of advance-at-end.

**Verified by** `dev/test_combat_driver.py`, `dev/test_combat_loop.py` (including its
`resume_recovery` scenario), `dev/test_combat_gate.py`, `dev/test_completeness.py`, and the tracker's
own `test/combat-tracker.test.ts` — all under the mock backend, which is the limit named at the top
of this doc.
