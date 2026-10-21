import { promises as fs } from "node:fs"
import * as path from "node:path"
import {
  addCondition,
  advanceTurn,
  burst,
  clearTimer,
  cone,
  createEncounter,
  damage,
  deathSave,
  describeCombatant,
  describeEncounter,
  distanceBetween,
  formatCaught,
  heal,
  line,
  move,
  remindEachTurn,
  remindIn,
  removeCondition,
  rollback,
  setDead,
  useReaction,
  type FiredObligation,
  type TrackerState,
} from "./combat/engine"

/**
 * `combat-tracker` — the file-backed adapter around the pure engine in `combat/engine.ts`
 * (design/combat.md § Tracker). opencode loads every direct child of `plugin/` as a plugin, so the
 * engine lives one directory down, out of the scan. This adapter is a thin ring: load state → call
 * the engine → save state → echo the roster.
 */

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

function statePath(directory: string): string {
  return path.join(directory, ".opencode", ".orchestrator", "combat-state.json")
}

async function loadState(directory: string): Promise<TrackerState> {
  const raw = await fs.readFile(statePath(directory), "utf-8")
  return JSON.parse(raw) as TrackerState
}

async function saveState(directory: string, state: TrackerState): Promise<void> {
  const p = statePath(directory)
  await fs.mkdir(path.dirname(p), { recursive: true })
  await fs.writeFile(p, JSON.stringify(state, null, 2), "utf-8")
}

async function deleteState(directory: string): Promise<void> {
  await fs.rm(statePath(directory), { force: true })
}

/** Load → mutate (engine call) → save → echo the roster. The shared shape of every mutator tool. */
async function withState(
  directory: string,
  mutate: (state: TrackerState) => string | void,
): Promise<string> {
  const state = await loadState(directory)
  const extra = mutate(state)
  await saveState(directory, state)
  return (extra ? extra + "\n\n" : "") + describeEncounter(state)
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

const ID = { type: "string", description: 'A combatant id, e.g. "pc" or "goblin-2".' }
const BEARING = "Bearing (n/ne/e/se/s/sw/w/nw)"

/** A tool's JSON-Schema input: an object with these properties, `required` naming the mandatory ones. */
function input(properties: Record<string, object> = {}, required: string[] = []) {
  return { type: "object", properties, required, additionalProperties: false }
}

/** Run a tool body, turning an engine error into text the model can read and act on. */
async function answer(body: () => Promise<string>) {
  try {
    return { content: await body() }
  } catch (e: any) {
    return { content: `Error: ${e.message}` }
  }
}

export default {
  id: "gm-combat-tracker",
  async setup(ctx) {
    const dir = ctx.location.directory
    await ctx.tool.transform((tools) => {
      // Called directly, not through code mode: the orchestrator reads these calls by name.
      const add = (tool: {
        name: string
        description: string
        input: object
        execute: (args: any) => Promise<{ content: string }>
      }) => tools.add({ ...tool, options: { codemode: false } })

      add({
        name: "start_encounter",
        description:
          "Start a new combat encounter with a roster of combatants in initiative order. " +
          'Give the PC id "pc". Repeated NPCs get auto-numbered ids (goblin x3 -> goblin-1..3).',
        input: input(
          {
            roster: {
              type: "array",
              description: 'Combatants in initiative order, PC included with id "pc".',
              items: input(
                {
                  id: { type: "string", description: 'Force a specific id, e.g. "pc" for the player character.' },
                  name: { type: "string", description: 'Display name, e.g. "goblin".' },
                  hp: { type: "number", description: "Starting hit points." },
                  hp_max: { type: "number", description: "Max hit points, defaults to hp." },
                  count: { type: "number", description: "How many of this combatant; ids get -1, -2, ... suffixes." },
                  distance: { type: "number", description: "Starting distance from the PC in feet, default 30." },
                  height: { type: "number", description: "Starting height relative to the PC in feet, default 0." },
                  direction: { type: "string", description: `Starting ${BEARING.toLowerCase()} from the PC, default n.` },
                },
                ["name", "hp"],
              ),
            },
            scene: { type: "string", description: 'Short description of the encounter, e.g. "goblin ambush on the forest road".' },
          },
          ["roster", "scene"],
        ),
        execute: (args) =>
          answer(async () => {
            const state = createEncounter(args.scene, args.roster)
            await saveState(dir, state)
            return describeEncounter(state)
          }),
      })

      add({
        name: "end_encounter",
        description: "End the current combat encounter and clear its state.",
        input: input(),
        execute: () =>
          answer(async () => {
            await deleteState(dir)
            return "Combat ended."
          }),
      })

      add({
        name: "damage",
        description: "Deal damage to a combatant. Does not mark an NPC dead — see set_dead.",
        input: input({ id: ID, amount: { type: "number", description: "Damage to apply, >= 0." } }, ["id", "amount"]),
        execute: (args) => answer(() => withState(dir, (state) => damage(state, args.id, args.amount))),
      })

      add({
        name: "heal",
        description: "Restore hit points to a combatant, capped at their max.",
        input: input({ id: ID, amount: { type: "number", description: "Healing to apply, >= 0." } }, ["id", "amount"]),
        execute: (args) => answer(() => withState(dir, (state) => heal(state, args.id, args.amount))),
      })

      add({
        name: "add_condition",
        description: "Apply a named condition to a combatant. The tracker returns the canonical effect text.",
        input: input({ id: ID, name: { type: "string", description: "e.g. prone, restrained, frightened." } }, ["id", "name"]),
        execute: (args) => answer(() => withState(dir, (state) => addCondition(state, args.id, args.name))),
      })

      add({
        name: "remove_condition",
        description: "Remove a named condition from a combatant.",
        input: input({ id: ID, name: { type: "string" } }, ["id", "name"]),
        execute: (args) => answer(() => withState(dir, (state) => removeCondition(state, args.id, args.name))),
      })

      add({
        name: "move",
        description:
          'Move a combatant. Moving "pc" fans out and re-syncs everyone else\'s distance/' +
          "direction against the new PC origin; moving anyone else is a plain absolute set. " +
          "Height is untouched by a PC move.",
        input: input(
          {
            id: ID,
            distance: { type: "number", description: 'Feet from the PC (or, for "pc", feet moved).' },
            height: { type: "number", description: 'Feet above/below the PC (ignored for "pc").' },
            direction: { type: "string", description: `${BEARING} — from the PC, or, for "pc", the direction moved.` },
          },
          ["id"],
        ),
        execute: (args) =>
          answer(() =>
            withState(dir, (state) =>
              move(state, args.id, { distance: args.distance, height: args.height, direction: args.direction }),
            ),
          ),
      })

      add({
        name: "set_dead",
        description:
          "Mark a combatant dead or alive. NPC death is your narrative call (0 hp doesn't auto-kill); " +
          "callable either direction to correct a mistake.",
        input: input({ id: ID, dead: { type: "boolean" } }, ["id", "dead"]),
        execute: (args) => answer(() => withState(dir, (state) => setDead(state, args.id, args.dead))),
      })

      add({
        name: "death_save",
        description:
          "Report one death saving throw for the PC at 0 hp. Three failures ends them; " +
          "three successes just stops the prompting.",
        input: input({ id: ID, success: { type: "boolean" } }, ["id", "success"]),
        execute: (args) => answer(() => withState(dir, (state) => deathSave(state, args.id, args.success))),
      })

      add({
        name: "use_reaction",
        description: "Spend a combatant's reaction. Resets automatically on their own turn.",
        input: input({ id: ID }, ["id"]),
        execute: (args) => answer(() => withState(dir, (state) => useReaction(state, args.id))),
      })

      add({
        name: "remind_in",
        description:
          "Set a one-shot reminder that fires after N future occurrences of the CURRENT " +
          "combatant's turn (e.g. a spell cast now that ends on the caster's turn in 3 rounds).",
        input: input(
          {
            rounds: { type: "number", description: "How many times the current turn-slot must recur." },
            note: { type: "string", description: "What to remember when it fires." },
          },
          ["rounds", "note"],
        ),
        execute: (args) =>
          answer(async () => {
            let id = 0
            const output = await withState(dir, (state) => {
              id = remindIn(state, args.rounds, args.note)
            })
            return `Timer ${id} set.\n\n${output}`
          }),
      })

      add({
        name: "remind_each_turn",
        description:
          "Set a recurring reminder that fires every time the named combatant's turn comes up " +
          "(save-ends conditions, per-round ticks). Optional owner auto-clears it on that owner's death.",
        input: input(
          {
            combatant: { type: "string", description: "Whose turn-slot fires this — often the target, not the caster." },
            note: { type: "string", description: "What to remember when it fires." },
            owner: { type: "string", description: "Auto-clear this timer when this combatant dies." },
          },
          ["combatant", "note"],
        ),
        execute: (args) =>
          answer(async () => {
            let id = 0
            const output = await withState(dir, (state) => {
              id = remindEachTurn(state, args.combatant, args.note, args.owner)
            })
            return `Timer ${id} set.\n\n${output}`
          }),
      })

      add({
        name: "clear_timer",
        description: "Remove a timer by id (dismissing a stale one, e.g. after its owner died).",
        input: input({ id: { type: "number" } }, ["id"]),
        execute: (args) => answer(() => withState(dir, (state) => clearTimer(state, args.id))),
      })

      add({
        name: "advance_turn",
        description: "Advance to the next combatant's turn. Fires any timers pinned to that slot.",
        input: input(),
        execute: () =>
          answer(async () => {
            let fired: FiredObligation[] = []
            const output = await withState(dir, (state) => {
              fired = advanceTurn(state).fired
            })
            if (!fired.length) return output
            const lines = fired.map((f) =>
              f.elapsed !== undefined
                ? `[timer ${f.id}] ${f.note} (elapsed ${f.elapsed} round(s))`
                : `[timer ${f.id}] ${f.note}`,
            )
            return `Fired:\n${lines.join("\n")}\n\n${output}`
          }),
      })

      add({
        name: "rollback",
        description:
          "Undo the in-flight action: roll pending back to the last committed state. Use when " +
          "interjecting with a reaction, before replaying the combatant's turn.",
        input: input(),
        execute: () => answer(() => withState(dir, (state) => rollback(state))),
      })

      add({
        name: "state",
        description: "Show the current encounter: round, whose turn it is, and the full roster.",
        input: input(),
        execute: () => answer(async () => describeEncounter(await loadState(dir))),
      })

      add({
        name: "describe",
        description:
          "Show the full picture on one combatant: hp, every condition's full effect text, " +
          "reaction state, death saves, position, and any timers pinned to their turn.",
        input: input({ id: ID }, ["id"]),
        execute: (args) => answer(async () => describeCombatant(await loadState(dir), args.id)),
      })

      add({
        name: "distance_between",
        description: "Approximate distance in feet between two non-PC combatants.",
        input: input({ a: ID, b: ID }, ["a", "b"]),
        execute: (args) => answer(async () => `${distanceBetween(await loadState(dir), args.a, args.b)} ft`),
      })

      add({
        name: "burst",
        description:
          "Which combatants a burst catches — any radius effect (a fireball, and every sphere, " +
          "cylinder, or cube). Centered on a point `distance` ft in `direction` from the PC " +
          "(distance 0 = centered on the PC; direction is then ignored). Returns everyone within " +
          "`radius` ft, the PC included if caught. A read — then apply damage to each with `damage`.",
        input: input(
          {
            distance: { type: "number", description: "Feet from the PC to the center; 0 centers it on the PC." },
            direction: { type: "string", description: `${BEARING} from the PC to the center; omit when distance is 0.` },
            radius: { type: "number", description: "Radius of the effect in feet." },
            height: { type: "number", description: "Center's height relative to the PC in feet." },
          },
          ["distance", "radius"],
        ),
        execute: (args) =>
          answer(async () => {
            const state = await loadState(dir)
            return formatCaught(state, burst(state, args))
          }),
      })

      add({
        name: "cone",
        description:
          "Which combatants a cone catches (a breath weapon, burning hands). It spreads from `origin` " +
          "(the caster — any combatant, whether or not it is their turn), `length` ft toward " +
          "`direction`. The origin is never caught. A read — then apply damage to each with `damage`.",
        input: input(
          {
            origin: { type: "string", description: "The combatant the cone spreads from (the caster's id)." },
            direction: { type: "string", description: `${BEARING} the cone points.` },
            length: { type: "number", description: "How far the cone reaches, in feet." },
          },
          ["origin", "direction", "length"],
        ),
        execute: (args) =>
          answer(async () => {
            const state = await loadState(dir)
            return formatCaught(state, cone(state, args.origin, args.direction, args.length))
          }),
      })

      add({
        name: "line",
        description:
          "Which combatants a line catches (a lightning bolt). It runs from `origin` (the caster — any " +
          "combatant, whether or not it is their turn), `length` ft toward `direction`, `width` ft " +
          "wide (default 5). The origin is never caught. A read — then apply damage to each with `damage`.",
        input: input(
          {
            origin: { type: "string", description: "The combatant the line runs from (the caster's id)." },
            direction: { type: "string", description: `${BEARING} the line runs.` },
            length: { type: "number", description: "How far the line reaches, in feet." },
            width: { type: "number", description: "Width of the line in feet; defaults to 5." },
          },
          ["origin", "direction", "length"],
        ),
        execute: (args) =>
          answer(async () => {
            const state = await loadState(dir)
            return formatCaught(state, line(state, args.origin, args.direction, args.length, args.width))
          }),
      })
    })
  },
}
