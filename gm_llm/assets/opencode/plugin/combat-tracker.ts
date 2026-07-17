import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
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
 * (COMBAT.md C0). This file is the one opencode auto-discovers and loads, so it exports **only**
 * the plugin: opencode's loader (`Glob.scan("{plugin,plugins}/*.{ts,js}")` → iterate every export)
 * treats each named export as a plugin, so the engine's helpers live one directory down, out of the
 * scan. This adapter is a thin ring: load state → call the engine → save state → echo the roster.
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

export const CombatTrackerPlugin: Plugin = async () => {
  return {
    tool: {
      start_encounter: tool({
        description:
          "Start a new combat encounter with a roster of combatants in initiative order. " +
          "Give the PC id \"pc\". Repeated NPCs get auto-numbered ids (goblin x3 -> goblin-1..3).",
        args: {
          roster: tool.schema
            .array(
              tool.schema.object({
                id: tool.schema
                  .string()
                  .optional()
                  .describe('Force a specific id, e.g. "pc" for the player character.'),
                name: tool.schema.string().describe('Display name, e.g. "goblin".'),
                hp: tool.schema.number().describe("Starting hit points."),
                hp_max: tool.schema.number().optional().describe("Max hit points, defaults to hp."),
                count: tool.schema
                  .number()
                  .optional()
                  .describe("How many of this combatant; ids get -1, -2, ... suffixes."),
                distance: tool.schema
                  .number()
                  .optional()
                  .describe("Starting distance from the PC in feet, default 30."),
                height: tool.schema
                  .number()
                  .optional()
                  .describe("Starting height relative to the PC in feet, default 0."),
                direction: tool.schema
                  .string()
                  .optional()
                  .describe("Starting bearing from the PC (n/ne/e/se/s/sw/w/nw), default n."),
              }),
            )
            .describe('Combatants in initiative order, PC included with id "pc".'),
          scene: tool.schema
            .string()
            .describe('Short description of the encounter, e.g. "goblin ambush on the forest road".'),
        },
        async execute(args, ctx) {
          try {
            const state = createEncounter(args.scene, args.roster)
            await saveState(ctx.directory, state)
            return { title: `Combat started: ${args.scene}`, output: describeEncounter(state) }
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      end_encounter: tool({
        description: "End the current combat encounter and clear its state.",
        args: {},
        async execute(_args, ctx) {
          await deleteState(ctx.directory)
          return "Combat ended."
        },
      }),

      damage: tool({
        description: "Deal damage to a combatant. Does not mark an NPC dead — see set_dead.",
        args: {
          id: tool.schema.string(),
          amount: tool.schema.number().describe("Damage to apply, >= 0."),
        },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) => damage(state, args.id, args.amount))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      heal: tool({
        description: "Restore hit points to a combatant, capped at their max.",
        args: {
          id: tool.schema.string(),
          amount: tool.schema.number().describe("Healing to apply, >= 0."),
        },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) => heal(state, args.id, args.amount))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      add_condition: tool({
        description:
          "Apply a named condition to a combatant. The tracker returns the canonical effect text.",
        args: {
          id: tool.schema.string(),
          name: tool.schema.string().describe("e.g. prone, restrained, frightened."),
        },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) =>
              addCondition(state, args.id, args.name),
            )
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      remove_condition: tool({
        description: "Remove a named condition from a combatant.",
        args: { id: tool.schema.string(), name: tool.schema.string() },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) =>
              removeCondition(state, args.id, args.name),
            )
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      move: tool({
        description:
          'Move a combatant. Moving "pc" fans out and re-syncs everyone else\'s distance/' +
          "direction against the new PC origin; moving anyone else is a plain absolute set. " +
          "Height is untouched by a PC move.",
        args: {
          id: tool.schema.string(),
          distance: tool.schema.number().optional().describe("Feet from the PC (or, for \"pc\", feet moved)."),
          height: tool.schema.number().optional().describe("Feet above/below the PC (ignored for \"pc\")."),
          direction: tool.schema
            .string()
            .optional()
            .describe("Bearing (n/ne/e/se/s/sw/w/nw) — from the PC, or, for \"pc\", the direction moved."),
        },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) =>
              move(state, args.id, {
                distance: args.distance,
                height: args.height,
                direction: args.direction,
              }),
            )
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      set_dead: tool({
        description:
          "Mark a combatant dead or alive. NPC death is your narrative call (0 hp doesn't auto-kill); " +
          "callable either direction to correct a mistake.",
        args: { id: tool.schema.string(), dead: tool.schema.boolean() },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) => setDead(state, args.id, args.dead))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      death_save: tool({
        description:
          "Report one death saving throw for the PC at 0 hp. Three failures ends them; " +
          "three successes just stops the prompting.",
        args: { id: tool.schema.string(), success: tool.schema.boolean() },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) =>
              deathSave(state, args.id, args.success),
            )
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      use_reaction: tool({
        description: "Spend a combatant's reaction. Resets automatically on their own turn.",
        args: { id: tool.schema.string() },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) => useReaction(state, args.id))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      remind_in: tool({
        description:
          "Set a one-shot reminder that fires after N future occurrences of the CURRENT " +
          "combatant's turn (e.g. a spell cast now that ends on the caster's turn in 3 rounds).",
        args: {
          rounds: tool.schema.number().describe("How many times the current turn-slot must recur."),
          note: tool.schema.string().describe("What to remember when it fires."),
        },
        async execute(args, ctx) {
          try {
            let id = 0
            const output = await withState(ctx.directory, (state) => {
              id = remindIn(state, args.rounds, args.note)
            })
            return `Timer ${id} set.\n\n${output}`
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      remind_each_turn: tool({
        description:
          "Set a recurring reminder that fires every time the named combatant's turn comes up " +
          "(save-ends conditions, per-round ticks). Optional owner auto-clears it on that owner's death.",
        args: {
          combatant: tool.schema.string().describe("Whose turn-slot fires this — often the target, not the caster."),
          note: tool.schema.string().describe("What to remember when it fires."),
          owner: tool.schema.string().optional().describe("Auto-clear this timer when this combatant dies."),
        },
        async execute(args, ctx) {
          try {
            let id = 0
            const output = await withState(ctx.directory, (state) => {
              id = remindEachTurn(state, args.combatant, args.note, args.owner)
            })
            return `Timer ${id} set.\n\n${output}`
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      clear_timer: tool({
        description: "Remove a timer by id (dismissing a stale one, e.g. after its owner died).",
        args: { id: tool.schema.number() },
        async execute(args, ctx) {
          try {
            return await withState(ctx.directory, (state) => clearTimer(state, args.id))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      advance_turn: tool({
        description: "Advance to the next combatant's turn. Fires any timers pinned to that slot.",
        args: {},
        async execute(_args, ctx) {
          try {
            let fired: FiredObligation[] = []
            const output = await withState(ctx.directory, (state) => {
              fired = advanceTurn(state).fired
            })
            if (!fired.length) return output
            const lines = fired.map((f) =>
              f.elapsed !== undefined
                ? `[timer ${f.id}] ${f.note} (elapsed ${f.elapsed} round(s))`
                : `[timer ${f.id}] ${f.note}`,
            )
            return `Fired:\n${lines.join("\n")}\n\n${output}`
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      rollback: tool({
        description:
          "Undo the in-flight action: roll pending back to the last committed state. Use when " +
          "interjecting with a reaction, before replaying the combatant's turn.",
        args: {},
        async execute(_args, ctx) {
          try {
            return await withState(ctx.directory, (state) => rollback(state))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      state: tool({
        description: "Show the current encounter: round, whose turn it is, and the full roster.",
        args: {},
        async execute(_args, ctx) {
          try {
            return describeEncounter(await loadState(ctx.directory))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      describe: tool({
        description:
          "Show the full picture on one combatant: hp, every condition's full effect text, " +
          "reaction state, death saves, position, and any timers pinned to their turn.",
        args: { id: tool.schema.string() },
        async execute(args, ctx) {
          try {
            return describeCombatant(await loadState(ctx.directory), args.id)
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      distance_between: tool({
        description: "Approximate distance in feet between two non-PC combatants.",
        args: { a: tool.schema.string(), b: tool.schema.string() },
        async execute(args, ctx) {
          try {
            const feet = distanceBetween(await loadState(ctx.directory), args.a, args.b)
            return `${feet} ft`
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      burst: tool({
        description:
          "Which combatants a burst catches — any radius effect (a fireball, and every sphere, " +
          "cylinder, or cube). Centered on a point `distance` ft in `direction` from the PC " +
          "(distance 0 = centered on the PC; direction is then ignored). Returns everyone within " +
          "`radius` ft, the PC included if caught. A read — then apply damage to each with `damage`.",
        args: {
          distance: tool.schema.number().describe("Feet from the PC to the center; 0 centers it on the PC."),
          direction: tool.schema
            .string()
            .optional()
            .describe("Bearing from the PC to the center (n/ne/e/se/s/sw/w/nw); omit when distance is 0."),
          radius: tool.schema.number().describe("Radius of the effect in feet."),
          height: tool.schema.number().optional().describe("Center's height relative to the PC in feet."),
        },
        async execute(args, ctx) {
          try {
            const state = await loadState(ctx.directory)
            return formatCaught(state, burst(state, args))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      cone: tool({
        description:
          "Which combatants a cone catches (a breath weapon, burning hands). It spreads from the " +
          "combatant whose turn it is, `length` ft toward `direction`. The caster is never caught. " +
          "A read — then apply damage to each with `damage`.",
        args: {
          direction: tool.schema.string().describe("Bearing the cone points (n/ne/e/se/s/sw/w/nw)."),
          length: tool.schema.number().describe("How far the cone reaches, in feet."),
        },
        async execute(args, ctx) {
          try {
            const state = await loadState(ctx.directory)
            return formatCaught(state, cone(state, args.direction, args.length))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),

      line: tool({
        description:
          "Which combatants a line catches (a lightning bolt). It runs from the combatant whose turn " +
          "it is, `length` ft toward `direction`, `width` ft wide (default 5). The caster is never " +
          "caught. A read — then apply damage to each with `damage`.",
        args: {
          direction: tool.schema.string().describe("Bearing the line runs (n/ne/e/se/s/sw/w/nw)."),
          length: tool.schema.number().describe("How far the line reaches, in feet."),
          width: tool.schema.number().optional().describe("Width of the line in feet; defaults to 5."),
        },
        async execute(args, ctx) {
          try {
            const state = await loadState(ctx.directory)
            return formatCaught(state, line(state, args.direction, args.length, args.width))
          } catch (e: any) {
            return `Error: ${e.message}`
          }
        },
      }),
    },
  }
}
