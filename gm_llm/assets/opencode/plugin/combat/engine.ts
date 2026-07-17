/**
 * combat-tracker engine — the pure, authoritative combat state machine (COMBAT.md C0).
 *
 * This module is deliberately fs-free and tool-free: every function operates on an in-memory
 * `TrackerState`, which is what makes it directly unit-testable without a model or opencode in the
 * loop. The plugin adapter (../combat-tracker.ts) wraps these with load/save/echo.
 *
 * It lives in a subdirectory so opencode's plugin auto-discovery — `Glob.scan("{plugin,plugins}/
 * *.{ts,js}")`, direct children only — never imports it as a plugin. The tracker owns deterministic
 * bookkeeping (HP, conditions, initiative, position, the one tracked resource — reaction — and
 * timers); the model owns judgment (whether an attack hits, whether an enemy flees, whether a
 * reaction applies).
 */

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export type Combatant = {
  id: string
  name: string
  hp: number
  hp_max: number
  dead: boolean // the only status bit; alive is simply !dead
  conditions: { name: string; effect: string }[]
  reaction: boolean // true = available; reset on this combatant's advance_turn
  death_saves?: { successes: number; failures: number } // present once "pc" hits 0 hp
  // World coordinates in feet on a shared plane; the PC is seeded at the origin. Storage is
  // Cartesian (exact, no accumulation); the model only ever sees the *egocentric* projection —
  // distance/direction/height vs. the PC — rendered on demand (see `ego`). z is height.
  x: number
  y: number
  z: number
}

export type Timer = {
  id: number
  combatant: string // whose turn-slot triggers this (dead-or-alive — initiative isn't pruned)
  kind: "in" | "each_turn"
  passes_remaining?: number // "in" only: decremented each time `combatant`'s turn comes up
  set_round: number // for `elapsed` on "each_turn" fires
  note: string
  owner?: string // auto-culled when this combatant dies
}

export type Frame = {
  // turn/round live INSIDE the frame (not top-level) so a commit/rollback snapshots them
  // with everything else: rollback restores the turn pointer too, which is what lets the
  // runner's turn end by advancing and still be cleanly replayed on an interject (COMBAT.md
  // "The combat loop"). next_timer_id stays top-level — it must never rewind, or a rolled-back
  // timer's id could be reused.
  turn: string
  round: number
  combatants: Record<string, Combatant>
  initiative: string[]
  timers: Timer[]
}

export type TrackerState = {
  encounter: string
  next_timer_id: number
  committed: Frame
  pending: Frame
}

export type FiredObligation = { id: number; note: string; elapsed?: number }

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

function requireCombatant(state: TrackerState, id: string): Combatant {
  const c = state.pending.combatants[id]
  if (!c) throw new Error(`unknown combatant: "${id}"`)
  return c
}

function slug(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

// ---------------------------------------------------------------------------
// Conditions — a bounded standard library, not free tags
// ---------------------------------------------------------------------------

export const CONDITION_LIBRARY: Record<string, string> = {
  blinded:
    "Can't see; automatically fails sight-based checks; attacks against it have advantage, its attacks have disadvantage.",
  charmed:
    "Can't attack the charmer or target it with harmful abilities/effects; the charmer has advantage on social checks against it.",
  deafened: "Can't hear; automatically fails hearing-based checks.",
  exhausted:
    "Cumulative levels impose escalating penalties (checks, speed, hp max, attacks, then death) — track the level in the note.",
  frightened:
    "Disadvantage on ability checks and attack rolls while the source of fear is in line of sight; can't willingly move closer to it.",
  grappled:
    "Speed becomes 0; ends if the grappler is incapacitated or the target is moved out of the grappler's reach.",
  incapacitated: "Can't take actions or reactions.",
  invisible:
    "Can't be seen without a special sense; heavily obscured for hiding purposes; attacks against it have disadvantage, its attacks have advantage.",
  paralyzed:
    "Incapacitated, can't move or speak; automatically fails Strength and Dexterity saves; attacks against it have advantage and are critical hits within 5 ft.",
  petrified:
    "Transformed, along with equipment, to stone; incapacitated, can't move or speak, unaware of surroundings; resistant to all damage; immune to poison and disease.",
  poisoned: "Disadvantage on attack rolls and ability checks.",
  prone:
    "Can only crawl (or stand, using half its movement); disadvantage on attack rolls; attacks against it have advantage within 5 ft, disadvantage otherwise.",
  restrained:
    "Speed becomes 0; disadvantage on attack rolls and Dexterity saves; attacks against it have advantage.",
  stunned:
    "Incapacitated, can't move, can speak only falteringly; automatically fails Strength and Dexterity saves; attacks against it have advantage.",
  unconscious:
    "Incapacitated, can't move or speak, unaware of surroundings, drops what it's holding, falls prone; automatically fails Strength and Dexterity saves; attacks against it have advantage and are critical hits within 5 ft.",
}

function normalizeConditionName(name: string): string {
  return name.trim().toLowerCase()
}

export function addCondition(state: TrackerState, id: string, name: string): void {
  const c = requireCombatant(state, id)
  const key = normalizeConditionName(name)
  const effect = CONDITION_LIBRARY[key]
  if (!effect) {
    const valid = Object.keys(CONDITION_LIBRARY).join(", ")
    throw new Error(`unknown condition "${name}" — valid conditions: ${valid}`)
  }
  if (c.conditions.some((x) => x.name === key)) return
  c.conditions.push({ name: key, effect })
}

export function removeCondition(state: TrackerState, id: string, name: string): void {
  const c = requireCombatant(state, id)
  const key = normalizeConditionName(name)
  c.conditions = c.conditions.filter((x) => x.name !== key)
}

// ---------------------------------------------------------------------------
// Position math — egocentric vs. the PC, Chebyshev distance (5e's untaxed diagonal)
// ---------------------------------------------------------------------------

const DIRECTIONS: Record<string, [number, number]> = {
  n: [0, 1],
  ne: [1, 1],
  e: [1, 0],
  se: [1, -1],
  s: [0, -1],
  sw: [-1, -1],
  w: [-1, 0],
  nw: [-1, 1],
}

const DIRECTION_ALIASES: Record<string, string> = {
  n: "n",
  north: "n",
  ne: "ne",
  northeast: "ne",
  e: "e",
  east: "e",
  se: "se",
  southeast: "se",
  s: "s",
  south: "s",
  sw: "sw",
  southwest: "sw",
  w: "w",
  west: "w",
  nw: "nw",
  northwest: "nw",
}

// Ordered by angle (atan2 degrees, 0-360) for directionForVector's snap-to-nearest-45.
const ANGLE_DIRECTIONS = ["e", "ne", "n", "nw", "w", "sw", "s", "se"]

export function normalizeDirection(input: string): string {
  const key = input.trim().toLowerCase().replace(/[\s-]/g, "")
  const canonical = DIRECTION_ALIASES[key]
  if (!canonical) {
    throw new Error(
      `unknown direction "${input}" — use n/ne/e/se/s/sw/w/nw or the full compass word`,
    )
  }
  return canonical
}

function vectorFor(direction: string, distance: number): [number, number] {
  const [dx, dy] = DIRECTIONS[direction]
  return [dx * distance, dy * distance]
}

function chebyshev(x: number, y: number): number {
  return Math.max(Math.abs(x), Math.abs(y))
}

function roundTo5(n: number): number {
  return Math.round(n / 5) * 5
}

function directionForVector(x: number, y: number): string {
  let angle = (Math.atan2(y, x) * 180) / Math.PI
  if (angle < 0) angle += 360
  const idx = Math.round(angle / 45) % 8
  return ANGLE_DIRECTIONS[idx]
}

export type Egocentric = { distance: number; direction?: string; height: number }

/** Project a combatant's world coords into the PC-relative frame the model actually sees. */
function ego(frame: Frame, c: Combatant): Egocentric {
  const pc = frame.combatants["pc"]
  const ox = pc?.x ?? 0
  const oy = pc?.y ?? 0
  const oz = pc?.z ?? 0
  const dx = c.x - ox
  const dy = c.y - oy
  const distance = roundTo5(chebyshev(dx, dy))
  // On top of the PC (distance 0), bearing is meaningless — omit it.
  return { distance, direction: distance > 0 ? directionForVector(dx, dy) : undefined, height: c.z - oz }
}

/** The egocentric projection of one combatant — for the tracker's reads and the checker. */
export function egocentric(state: TrackerState, id: string): Egocentric {
  return ego(state.pending, requireCombatant(state, id))
}

/**
 * move(id, ...): "pc" shifts the origin — every other combatant's *displayed* position re-syncs for
 * free because storage is world-absolute (no fan-out loop, no accumulated rounding). Anyone else is a
 * plain absolute set expressed in the egocentric frame the model speaks. Height is untouched by a PC
 * move; a lone height change on an NPC leaves its x/y alone.
 */
export function move(
  state: TrackerState,
  id: string,
  opts: { distance?: number; height?: number; direction?: string },
): void {
  const c = requireCombatant(state, id)
  const pc = state.pending.combatants["pc"]

  if (id === "pc") {
    const { distance, direction } = opts
    if (distance === undefined || direction === undefined) {
      throw new Error("moving the PC requires both distance and direction")
    }
    const [dx, dy] = vectorFor(normalizeDirection(direction), distance)
    c.x += dx
    c.y += dy
    return
  }

  if (opts.height !== undefined) c.z = (pc?.z ?? 0) + opts.height
  if (opts.distance !== undefined || opts.direction !== undefined) {
    const current = ego(state.pending, c)
    const distance = opts.distance ?? current.distance
    const direction = opts.direction ? normalizeDirection(opts.direction) : current.direction ?? "n"
    const [dx, dy] = vectorFor(direction, distance)
    c.x = (pc?.x ?? 0) + dx
    c.y = (pc?.y ?? 0) + dy
  }
}

/** Exact Chebyshev distance between any two combatants, derived from world coords. */
export function distanceBetween(state: TrackerState, a: string, b: string): number {
  const ca = requireCombatant(state, a)
  const cb = requireCombatant(state, b)
  return roundTo5(chebyshev(ca.x - cb.x, ca.y - cb.y))
}

// ---------------------------------------------------------------------------
// Area-of-effect shape queries — the model places the aim in egocentric terms;
// the tracker does the geometry over the exact stored coords and returns the
// caught combatants (initiative order). Pure reads: the model applies damage to
// each hit with `damage`. No coordinate ever leaves the tracker.
// ---------------------------------------------------------------------------

const CONE_HALF_ANGLE = Math.atan(0.5) // 5e cone: width at a point equals its distance from origin.

function livingCombatants(frame: Frame): Combatant[] {
  return frame.initiative.map((id) => frame.combatants[id]).filter((c): c is Combatant => !!c && !c.dead)
}

/**
 * burst(...): everyone within `radius` ft of a point placed `distance` ft `direction` from the PC
 * (distance 0 = centered on the PC). Covers every radius footprint — sphere, cylinder, cube. The PC
 * is caught like anyone else if in range; nobody is exempt (unlike cone/line, a burst has no caster
 * origin — it is placed).
 */
export function burst(
  state: TrackerState,
  opts: { distance: number; direction?: string; radius: number; height?: number },
): Combatant[] {
  const frame = state.pending
  const pc = frame.combatants["pc"]
  const ox = pc?.x ?? 0
  const oy = pc?.y ?? 0
  const oz = pc?.z ?? 0
  let cx = ox
  let cy = oy
  if (opts.distance > 0) {
    if (!opts.direction) throw new Error("a burst away from the PC (distance > 0) needs a direction")
    const [dx, dy] = vectorFor(normalizeDirection(opts.direction), opts.distance)
    cx = ox + dx
    cy = oy + dy
  }
  const cz = oz + (opts.height ?? 0)
  return livingCombatants(frame).filter(
    (c) => Math.max(chebyshev(c.x - cx, c.y - cy), Math.abs(c.z - cz)) <= opts.radius,
  )
}

/**
 * cone(...): everyone in a cone spreading from `origin` (any combatant — the caster — whether or not
 * it is their turn), `length` ft toward `direction`. The origin is never caught. 5e cone geometry: a
 * target is in if its bearing from the origin is within the cone's half-angle of `direction` and it is
 * within `length`.
 */
export function cone(state: TrackerState, origin: string, direction: string, length: number): Combatant[] {
  const src = requireCombatant(state, origin)
  const [ax, ay] = DIRECTIONS[normalizeDirection(direction)]
  const alen = Math.hypot(ax, ay)
  return livingCombatants(state.pending).filter((c) => {
    if (c.id === src.id) return false
    const vx = c.x - src.x
    const vy = c.y - src.y
    const d = Math.hypot(vx, vy)
    if (d === 0 || d > length) return false
    const angle = Math.acos(Math.max(-1, Math.min(1, (vx * ax + vy * ay) / (d * alen))))
    return angle <= CONE_HALF_ANGLE + 1e-9
  })
}

/**
 * line(...): everyone in a line from `origin` (any combatant — the caster — whether or not it is their
 * turn), `length` ft toward `direction`, `width` ft wide (default 5). The origin is never caught. A
 * target is in if its projection onto the axis falls within [0, length] and its perpendicular offset is
 * within half the width.
 */
export function line(
  state: TrackerState,
  origin: string,
  direction: string,
  length: number,
  width = 5,
): Combatant[] {
  const src = requireCombatant(state, origin)
  const [ax, ay] = DIRECTIONS[normalizeDirection(direction)]
  const alen = Math.hypot(ax, ay)
  const nx = ax / alen
  const ny = ay / alen
  const half = width / 2
  return livingCombatants(state.pending).filter((c) => {
    if (c.id === src.id) return false
    const vx = c.x - src.x
    const vy = c.y - src.y
    const axial = vx * nx + vy * ny
    if (axial < 0 || axial > length) return false
    return Math.abs(vx * -ny + vy * nx) <= half + 1e-9
  })
}

/** Render an AoE query's caught combatants as egocentric lines (the roster echo's shape). */
export function formatCaught(state: TrackerState, caught: Combatant[]): string {
  if (!caught.length) return "No combatants caught."
  return caught
    .map((c) => {
      if (c.id === "pc") return "pc (you)"
      const { distance, direction } = ego(state.pending, c)
      return `${c.id}: ${distance} ft ${direction ?? ""}`.trim()
    })
    .join("\n")
}

// ---------------------------------------------------------------------------
// HP, death, reaction
// ---------------------------------------------------------------------------

export function damage(state: TrackerState, id: string, amount: number): void {
  if (amount < 0) throw new Error("damage amount must be >= 0")
  const c = requireCombatant(state, id)
  const before = c.hp
  c.hp = Math.max(0, before - amount)

  // 5e massive-damage rule: excess damage beyond what it took to reach 0 kills outright,
  // PC included — genuinely deterministic, so it's the one auto-kill the tracker applies.
  const excess = amount - before
  if (excess >= c.hp_max) {
    c.dead = true
    return
  }

  if (c.hp === 0 && id === "pc" && !c.death_saves) {
    c.death_saves = { successes: 0, failures: 0 }
  }
}

export function heal(state: TrackerState, id: string, amount: number): void {
  if (amount < 0) throw new Error("heal amount must be >= 0")
  const c = requireCombatant(state, id)
  c.hp = Math.min(c.hp_max, c.hp + amount)
  // Regaining any hp from 0 ends the dying state — the death-save tally resets (5e).
  if (c.hp > 0 && c.death_saves) delete c.death_saves
}

/** NPC death is the model's narrative call; the PC's is derived via death_save/massive damage. */
export function setDead(state: TrackerState, id: string, dead: boolean): void {
  const c = requireCombatant(state, id)
  c.dead = dead
  if (dead) state.pending.timers = state.pending.timers.filter((t) => t.owner !== id)
}

export function deathSave(state: TrackerState, id: string, success: boolean): void {
  const c = requireCombatant(state, id)
  if (!c.death_saves) c.death_saves = { successes: 0, failures: 0 }
  if (success) c.death_saves.successes++
  else c.death_saves.failures++
  if (c.death_saves.failures >= 3) c.dead = true
}

export function useReaction(state: TrackerState, id: string): void {
  requireCombatant(state, id).reaction = false
}

// ---------------------------------------------------------------------------
// Initiative, timers — anchored to a turn-slot, not a round-boundary
// ---------------------------------------------------------------------------

export function remindIn(state: TrackerState, rounds: number, note: string): number {
  const id = state.next_timer_id++
  state.pending.timers.push({
    id,
    combatant: state.pending.turn,
    kind: "in",
    passes_remaining: rounds,
    set_round: state.pending.round,
    note,
  })
  return id
}

export function remindEachTurn(
  state: TrackerState,
  combatant: string,
  note: string,
  owner?: string,
): number {
  requireCombatant(state, combatant)
  const id = state.next_timer_id++
  state.pending.timers.push({
    id,
    combatant,
    kind: "each_turn",
    set_round: state.pending.round,
    note,
    owner,
  })
  return id
}

export function clearTimer(state: TrackerState, id: number): void {
  state.pending.timers = state.pending.timers.filter((t) => t.id !== id)
}

/**
 * Steps one slot through initiative. A dead combatant still occupies their slot — their
 * initiative is still "passed," so a timer pinned to them still counts down/fires on schedule.
 * `round` only increments when the walk wraps back to the top of initiative.
 */
export function advanceTurn(
  state: TrackerState,
): { turn: string; round: number; fired: FiredObligation[] } {
  const frame = state.pending
  const idx = frame.initiative.indexOf(frame.turn)
  const nextIdx = (idx + 1) % frame.initiative.length
  if (nextIdx === 0) frame.round++
  frame.turn = frame.initiative[nextIdx]

  const entering = frame.combatants[frame.turn]
  if (entering) entering.reaction = true

  const fired: FiredObligation[] = []
  const remaining: Timer[] = []
  for (const t of frame.timers) {
    if (t.combatant !== frame.turn) {
      remaining.push(t)
      continue
    }
    if (t.kind === "each_turn") {
      fired.push({ id: t.id, note: t.note, elapsed: frame.round - t.set_round })
      remaining.push(t)
    } else {
      const left = (t.passes_remaining ?? 1) - 1
      if (left <= 0) {
        fired.push({ id: t.id, note: t.note })
      } else {
        t.passes_remaining = left
        remaining.push(t)
      }
    }
  }
  frame.timers = remaining

  return { turn: frame.turn, round: frame.round, fired }
}

export function rollback(state: TrackerState): void {
  state.pending = clone(state.committed)
}

// ---------------------------------------------------------------------------
// Roster construction and echo
// ---------------------------------------------------------------------------

export type RosterEntry = {
  id?: string
  name: string
  hp: number
  hp_max?: number
  count?: number
  distance?: number
  height?: number
  direction?: string
}

export function createEncounter(scene: string, roster: RosterEntry[]): TrackerState {
  // Pre-pass: only suffix ids (goblin-1, goblin-2, ...) when a name is genuinely repeated.
  const totals: Record<string, number> = {}
  for (const entry of roster) {
    if (entry.id) continue
    const key = slug(entry.name)
    totals[key] = (totals[key] ?? 0) + (entry.count ?? 1)
  }

  const seen: Record<string, number> = {}
  const combatants: Record<string, Combatant> = {}
  const initiative: string[] = []

  for (const entry of roster) {
    const count = entry.count ?? 1
    const key = slug(entry.name)
    for (let i = 0; i < count; i++) {
      let id: string
      if (entry.id) {
        id = entry.id
      } else {
        seen[key] = (seen[key] ?? 0) + 1
        id = totals[key] > 1 ? `${key}-${seen[key]}` : key
      }

      const combatant: Combatant = {
        id,
        name: entry.name,
        hp: entry.hp,
        hp_max: entry.hp_max ?? entry.hp,
        dead: false,
        conditions: [],
        reaction: true,
        x: 0,
        y: 0,
        z: 0,
      }
      if (id !== "pc") {
        // Seed from the egocentric input; the PC is at the origin, so it doubles as world coords.
        const [dx, dy] = vectorFor(normalizeDirection(entry.direction ?? "n"), entry.distance ?? 30)
        combatant.x = dx
        combatant.y = dy
        combatant.z = entry.height ?? 0
      }
      combatants[id] = combatant
      initiative.push(id)
    }
  }

  const frame: Frame = { turn: initiative[0], round: 1, combatants, initiative, timers: [] }
  return {
    encounter: scene,
    next_timer_id: 1,
    committed: clone(frame),
    pending: clone(frame),
  }
}

/** Compact, one-line-per-combatant roster — rides along on every mutator's output. */
export function formatRoster(frame: Frame): string {
  return frame.initiative
    .map((id) => {
      const c = frame.combatants[id]
      if (!c) return `${id}: (unknown)`
      if (c.dead) return `${id}: dead`
      const bits = [`${c.hp}/${c.hp_max} hp`]
      if (c.conditions.length) bits.push(c.conditions.map((x) => x.name).join(", "))
      if (!c.reaction) bits.push("reaction used")
      if (c.id !== "pc") {
        const { distance, direction } = ego(frame, c)
        bits.push(`${distance} ft ${direction ?? ""}`.trim())
      }
      return `${id}: ${bits.join(", ")}`
    })
    .join("\n")
}

export function describeEncounter(state: TrackerState): string {
  return `Round ${state.pending.round} — ${state.pending.turn}'s turn\n${formatRoster(state.pending)}`
}

/** The full, human-readable picture on one combatant — describe(id)'s payload. */
export function describeCombatant(state: TrackerState, id: string): string {
  const c = requireCombatant(state, id)
  if (c.dead) return `${c.name} (${c.id}): dead`

  const lines = [`${c.name} (${c.id})`, `HP: ${c.hp}/${c.hp_max}`]
  lines.push(
    c.conditions.length
      ? `Conditions:\n${c.conditions.map((x) => `  - ${x.name}: ${x.effect}`).join("\n")}`
      : "Conditions: none",
  )
  lines.push(`Reaction: ${c.reaction ? "available" : "used"}`)
  if (c.death_saves) {
    lines.push(
      `Death saves: ${c.death_saves.successes} success(es), ${c.death_saves.failures} failure(s)`,
    )
  }
  if (c.id !== "pc") {
    const { distance, direction, height } = ego(state.pending, c)
    const pos = [`${distance} ft`, direction].filter(Boolean).join(" ")
    lines.push(`Position: ${pos}${height ? `, height ${height} ft` : ""}`)
  }
  // Obligations that fire on this combatant's own turn — so a dropped timer stays visible on demand.
  const own = state.pending.timers.filter((t) => t.combatant === id)
  if (own.length) {
    lines.push(`Timers on this turn:\n${own.map((t) => `  - [${t.id}] ${t.note}`).join("\n")}`)
  }
  return lines.join("\n")
}
