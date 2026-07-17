import { describe, expect, it } from "bun:test"
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
  distanceBetween,
  egocentric,
  formatCaught,
  formatRoster,
  heal,
  line,
  move,
  normalizeDirection,
  remindEachTurn,
  remindIn,
  removeCondition,
  rollback,
  setDead,
  useReaction,
  type TrackerState,
} from "../plugin/combat/engine"

// A representative 3-combatant encounter: pc + two positioned goblins.
function encounter(): TrackerState {
  return createEncounter("goblin ambush", [
    { id: "pc", name: "Dallid", hp: 24, hp_max: 31 },
    { name: "goblin", hp: 12, count: 2, distance: 30, direction: "e" },
  ])
}

describe("start_encounter / end_encounter", () => {
  it("assigns stable, auto-numbered ids and preserves initiative order", () => {
    const s = createEncounter("goblin ambush", [
      { id: "pc", name: "Dallid", hp: 24, hp_max: 31 },
      { name: "goblin", hp: 12, count: 3 },
      { name: "orc", hp: 20 },
    ])
    expect(s.pending.initiative).toEqual(["pc", "goblin-1", "goblin-2", "goblin-3", "orc"])
    expect(s.pending.combatants["goblin-1"].name).toBe("goblin")
    expect(s.pending.combatants["orc"].id).toBe("orc") // no suffix for a lone instance
    expect(s.pending.round).toBe(1)
    expect(s.pending.turn).toBe("pc")
    expect(s.committed).toEqual(s.pending)
  })

  it("defaults hp_max to hp and seeds NPC position from egocentric input; the PC sits at the origin", () => {
    const s = encounter()
    expect(s.pending.combatants["goblin-1"].hp_max).toBe(12)
    expect(egocentric(s, "goblin-1")).toEqual({ distance: 30, direction: "e", height: 0 })
    // 30 ft east -> world (30, 0); the PC is the origin.
    expect(s.pending.combatants["goblin-1"]).toMatchObject({ x: 30, y: 0, z: 0 })
    expect(s.pending.combatants["pc"]).toMatchObject({ x: 0, y: 0, z: 0 })
  })
})

describe("damage / heal", () => {
  it("clamps hp at 0 and 0 does not auto-kill an NPC", () => {
    const s = encounter()
    damage(s, "goblin-1", 20) // hp 12 -> 0, excess 8 < hp_max 12
    expect(s.pending.combatants["goblin-1"].hp).toBe(0)
    expect(s.pending.combatants["goblin-1"].dead).toBe(false)
  })

  it("massive damage (excess >= hp_max) kills an NPC outright", () => {
    const s = encounter()
    damage(s, "goblin-1", 30) // excess 18 >= hp_max 12
    expect(s.pending.combatants["goblin-1"].dead).toBe(true)
  })

  it("massive damage applies to the PC too, bypassing death saves", () => {
    const s = encounter()
    damage(s, "pc", 60) // excess 36 >= hp_max 31
    expect(s.pending.combatants["pc"].dead).toBe(true)
    expect(s.pending.combatants["pc"].death_saves).toBeUndefined()
  })

  it("brings the PC to 0 hp without killing them, seeding death_saves", () => {
    const s = encounter()
    damage(s, "pc", 24) // excess 0
    expect(s.pending.combatants["pc"].hp).toBe(0)
    expect(s.pending.combatants["pc"].dead).toBe(false)
    expect(s.pending.combatants["pc"].death_saves).toEqual({ successes: 0, failures: 0 })
  })

  it("heal clamps at hp_max", () => {
    const s = encounter()
    damage(s, "goblin-1", 10)
    heal(s, "goblin-1", 100)
    expect(s.pending.combatants["goblin-1"].hp).toBe(12)
  })

  it("healing the PC above 0 clears the dying death-save tally", () => {
    const s = encounter()
    damage(s, "pc", 24) // 0 hp, death_saves seeded
    deathSave(s, "pc", false)
    heal(s, "pc", 5)
    expect(s.pending.combatants["pc"].hp).toBe(5)
    expect(s.pending.combatants["pc"].death_saves).toBeUndefined()
  })

  it("healing to exactly 0 leaves the dying tally intact", () => {
    const s = encounter()
    damage(s, "pc", 24)
    heal(s, "pc", 0)
    expect(s.pending.combatants["pc"].death_saves).toEqual({ successes: 0, failures: 0 })
  })
})

describe("set_dead / death_save", () => {
  it("set_dead is a plain narrative toggle, either direction", () => {
    const s = encounter()
    setDead(s, "goblin-1", true)
    expect(s.pending.combatants["goblin-1"].dead).toBe(true)
    setDead(s, "goblin-1", false)
    expect(s.pending.combatants["goblin-1"].dead).toBe(false)
  })

  it("three death-save failures kills the PC", () => {
    const s = encounter()
    damage(s, "pc", 24)
    deathSave(s, "pc", false)
    deathSave(s, "pc", false)
    expect(s.pending.combatants["pc"].dead).toBe(false)
    deathSave(s, "pc", false)
    expect(s.pending.combatants["pc"].dead).toBe(true)
  })

  it("three death-save successes stabilize without a special status", () => {
    const s = encounter()
    damage(s, "pc", 24)
    deathSave(s, "pc", true)
    deathSave(s, "pc", true)
    deathSave(s, "pc", true)
    expect(s.pending.combatants["pc"].dead).toBe(false)
    expect(s.pending.combatants["pc"].hp).toBe(0)
    expect(s.pending.combatants["pc"].death_saves).toEqual({ successes: 3, failures: 0 })
  })
})

describe("add_condition / remove_condition", () => {
  it("looks up the bounded library and echoes full effect text, case/space-insensitively", () => {
    const s = encounter()
    addCondition(s, "goblin-1", "PRONE")
    expect(s.pending.combatants["goblin-1"].conditions).toEqual([
      { name: "prone", effect: expect.stringContaining("crawl") },
    ])
  })

  it("rejects an unknown condition with the valid list", () => {
    const s = encounter()
    expect(() => addCondition(s, "goblin-1", "smug")).toThrow(/unknown condition/)
  })

  it("removes a condition", () => {
    const s = encounter()
    addCondition(s, "goblin-1", "prone")
    removeCondition(s, "goblin-1", "prone")
    expect(s.pending.combatants["goblin-1"].conditions).toEqual([])
  })
})

describe("move", () => {
  it("moves an NPC as a plain absolute egocentric set, leaving unspecified axes alone", () => {
    const s = encounter()
    move(s, "goblin-1", { height: 10 })
    expect(egocentric(s, "goblin-1")).toEqual({ distance: 30, direction: "e", height: 10 }) // x/y untouched
    move(s, "goblin-1", { distance: 15, direction: "sw" })
    expect(egocentric(s, "goblin-1")).toEqual({ distance: 15, direction: "sw", height: 10 })
  })

  it("a lone distance change keeps the NPC's current bearing", () => {
    const s = encounter() // goblin-1 at 30 ft e
    move(s, "goblin-1", { distance: 45 })
    expect(egocentric(s, "goblin-1")).toMatchObject({ distance: 45, direction: "e" })
  })

  it("a PC move re-syncs every other combatant's displayed position (origin shift, no accumulation)", () => {
    const s = createEncounter("origin-shift test", [
      { id: "pc", name: "Dallid", hp: 24, hp_max: 31 },
      { id: "goblin-1", name: "goblin", hp: 12, distance: 30, direction: "e" }, // world (30, 0)
      { id: "goblin-2", name: "goblin", hp: 12, distance: 20, direction: "n" }, // world (0, 20)
    ])
    move(s, "goblin-2", { height: 10 })

    move(s, "pc", { distance: 20, direction: "e" }) // PC origin -> (20, 0)

    // goblin-1: (30,0) vs (20,0) -> 10 ft e
    expect(egocentric(s, "goblin-1")).toEqual({ distance: 10, direction: "e", height: 0 })
    // goblin-2: (0,20) vs (20,0) -> (-20,20) -> 20 ft nw, height preserved
    expect(egocentric(s, "goblin-2")).toEqual({ distance: 20, direction: "nw", height: 10 })
    // world coords are untouched by a PC move — only the origin moved
    expect(s.pending.combatants["goblin-1"]).toMatchObject({ x: 30, y: 0 })
  })

  it("drops the bearing when a PC move lands a combatant on top of them", () => {
    const s = createEncounter("overlap test", [
      { id: "pc", name: "Dallid", hp: 24, hp_max: 31 },
      { id: "goblin-1", name: "goblin", hp: 12, distance: 20, direction: "e" }, // world (20, 0)
    ])
    move(s, "pc", { distance: 20, direction: "e" }) // PC steps onto the goblin
    expect(egocentric(s, "goblin-1")).toMatchObject({ distance: 0, direction: undefined })
  })

  it("requires both distance and direction to move the PC", () => {
    const s = encounter()
    expect(() => move(s, "pc", { distance: 10 })).toThrow(/requires both/)
  })
})

describe("reaction", () => {
  it("resets to true on the combatant's own advance_turn; use_reaction spends it", () => {
    const s = encounter() // initiative: pc, goblin-1, goblin-2
    useReaction(s, "goblin-1")
    expect(s.pending.combatants["goblin-1"].reaction).toBe(false)
    advanceTurn(s) // -> goblin-1
    expect(s.pending.combatants["goblin-1"].reaction).toBe(true)
  })
})

describe("timers", () => {
  it("remind_in binds to the calling combatant's turn-slot and fires on the Nth recurrence", () => {
    const s = encounter() // initiative: pc, goblin-1, goblin-2; turn starts at pc
    remindIn(s, 2, "bless ends")

    const results = [
      advanceTurn(s), // -> goblin-1
      advanceTurn(s), // -> goblin-2
      advanceTurn(s), // -> pc (round 2), 1st recurrence of pc's slot
      advanceTurn(s), // -> goblin-1
      advanceTurn(s), // -> goblin-2
      advanceTurn(s), // -> pc (round 3), 2nd recurrence -> fires
    ]
    const fireRounds = results.map((r) => r.fired.length > 0)
    expect(fireRounds).toEqual([false, false, false, false, false, true])
    expect(results[5].fired[0].note).toBe("bless ends")
    expect(s.pending.timers).toEqual([]) // auto-cleared after firing
  })

  it("still fires on a dead combatant's slot — initiative isn't pruned", () => {
    const s = encounter()
    setDead(s, "goblin-1", true)
    remindIn(s, 1, "poison ticks") // bound to pc's slot (current turn)
    advanceTurn(s) // -> goblin-1 (dead, but still occupies its slot)
    advanceTurn(s) // -> goblin-2
    const { fired } = advanceTurn(s) // -> pc, 1st recurrence -> fires
    expect(fired).toEqual([{ id: expect.any(Number), note: "poison ticks" }])
  })

  it("remind_each_turn fires every recurrence of the named combatant's slot with correct elapsed", () => {
    const s = encounter()
    remindEachTurn(s, "goblin-2", "concentration: flaming sphere")
    advanceTurn(s) // -> goblin-1
    const first = advanceTurn(s) // -> goblin-2, round 1, elapsed 0
    expect(first.fired).toEqual([{ id: expect.any(Number), note: "concentration: flaming sphere", elapsed: 0 }])

    advanceTurn(s) // -> pc, round 2
    advanceTurn(s) // -> goblin-1
    const second = advanceTurn(s) // -> goblin-2, round 2, elapsed 1
    expect(second.fired[0].elapsed).toBe(1)
  })

  it("clear_timer removes a timer by id", () => {
    const s = encounter()
    const id = remindIn(s, 1, "note")
    clearTimer(s, id)
    expect(s.pending.timers).toEqual([])
  })

  it("auto-culls an owned timer when its owner dies", () => {
    const s = encounter()
    remindEachTurn(s, "goblin-2", "concentration", "goblin-1")
    setDead(s, "goblin-1", true)
    expect(s.pending.timers).toEqual([])
  })
})

describe("rollback", () => {
  it("restores pending from committed after a sequence of forward mutators", () => {
    const s = encounter()
    s.committed = JSON.parse(JSON.stringify(s.pending)) // simulate an orchestrator commit
    damage(s, "goblin-1", 5)
    addCondition(s, "goblin-1", "prone")
    useReaction(s, "goblin-1")

    rollback(s)

    expect(s.pending.combatants["goblin-1"].hp).toBe(12)
    expect(s.pending.combatants["goblin-1"].conditions).toEqual([])
    expect(s.pending.combatants["goblin-1"].reaction).toBe(true)
  })
})

describe("distance_between / describe", () => {
  it("distance_between is exact Chebyshev between two world points, not a lossy projection", () => {
    const s = createEncounter("distance test", [
      { id: "pc", name: "Dallid", hp: 24, hp_max: 31 },
      { id: "goblin-1", name: "goblin", hp: 12, distance: 30, direction: "e" }, // (30, 0)
      { id: "goblin-2", name: "goblin", hp: 12, distance: 20, direction: "n" }, // (0, 20)
    ])
    // max(|30-0|, |0-20|) = 30
    expect(distanceBetween(s, "goblin-1", "goblin-2")).toBe(30)
  })

  it("describe gives full condition text, reaction state, and position — not a JSON dump", () => {
    const s = encounter()
    addCondition(s, "goblin-1", "restrained")
    const text = describeCombatant(s, "goblin-1")
    expect(text).toContain("restrained")
    expect(text).toContain("Speed becomes 0") // full effect text, not just the name
    expect(text).toContain("Reaction: available")
    expect(text).toContain("30 ft e")
    expect(text).not.toMatch(/^\{/) // prose, not JSON
  })

  it("surfaces timers pinned to the combatant's own turn", () => {
    const s = encounter()
    const id = remindEachTurn(s, "goblin-1", "save vs. poison (ends)")
    const text = describeCombatant(s, "goblin-1")
    expect(text).toContain(`[${id}] save vs. poison (ends)`)
    // a timer on someone else's slot doesn't show here
    expect(describeCombatant(s, "goblin-2")).not.toContain("save vs. poison")
  })
})

describe("normalizeDirection", () => {
  it("accepts abbreviations, full words, and is case/space-insensitive", () => {
    expect(normalizeDirection("NE")).toBe("ne")
    expect(normalizeDirection("northeast")).toBe("ne")
    expect(normalizeDirection(" North East ")).toBe("ne")
  })

  it("rejects anything else", () => {
    expect(() => normalizeDirection("sideways")).toThrow(/unknown direction/)
  })
})

describe("formatRoster", () => {
  it("is compact prose, one line per combatant, not JSON", () => {
    const s = encounter()
    const text = formatRoster(s.pending)
    expect(text.split("\n")).toHaveLength(3)
    expect(text).toContain("pc: 24/31 hp")
    expect(text).toContain("goblin-1: 12/12 hp, 30 ft e")
  })
})

// A cross-shaped test board around the PC at the origin:
//   a = 30 ft E (30,0)   b = 30 ft N (0,30)   c = 60 ft E (60,0)   d = 30 ft NE (30,30)
function aoeBoard(): TrackerState {
  return createEncounter("aoe test", [
    { id: "pc", name: "PC", hp: 30 },
    { id: "a", name: "a", hp: 10, distance: 30, direction: "e" },
    { id: "b", name: "b", hp: 10, distance: 30, direction: "n" },
    { id: "c", name: "c", hp: 10, distance: 60, direction: "e" },
    { id: "d", name: "d", hp: 10, distance: 30, direction: "ne" },
  ])
}

const ids = (cs: { id: string }[]) => cs.map((c) => c.id).sort()

describe("burst", () => {
  it("catches everyone within radius of a placed point, boundary inclusive", () => {
    const s = aoeBoard()
    // Centered on `a` (30 ft E), radius 10: only `a` — the PC 30 ft off is not caught, proving the
    // burst is placed away from the origin, not centered on the PC.
    expect(ids(burst(s, { distance: 30, direction: "e", radius: 10 }))).toEqual(["a"])
    // Radius 30 (Chebyshev): every other combatant sits exactly 30 ft from `a` on this board — all in,
    // boundary inclusive, the PC included.
    expect(ids(burst(s, { distance: 30, direction: "e", radius: 30 }))).toEqual(["a", "b", "c", "d", "pc"])
  })

  it("centered on the PC (distance 0) catches the PC and needs no direction", () => {
    const s = aoeBoard()
    expect(ids(burst(s, { distance: 0, radius: 30 }))).toEqual(["a", "b", "d", "pc"])
    expect(ids(burst(s, { distance: 0, radius: 20 }))).toEqual(["pc"])
  })

  it("rejects a non-PC-centered burst with no direction", () => {
    expect(() => burst(aoeBoard(), { distance: 30, radius: 10 })).toThrow(/needs a direction/)
  })
})

describe("cone", () => {
  it("spreads from the given origin within its half-angle, excluding the caster", () => {
    const s = aoeBoard()
    // From the PC, eastward: reaches the two due-east foes; the northern and NE ones are outside.
    expect(ids(cone(s, "pc", "e", 60))).toEqual(["a", "c"])
    expect(ids(cone(s, "pc", "e", 30))).toEqual(["a"]) // length bounds out the 60-ft `c`
  })

  it("originates from ANY combatant, not just whoever's turn it is", () => {
    const s = aoeBoard() // still the PC's turn — but an off-turn combatant can be the origin
    // `a` at (30,0) breathes east toward `c` (60,0): reaches c, not the PC behind it, never the caster.
    expect(ids(cone(s, "a", "e", 40))).toEqual(["c"])
    expect(s.pending.turn).toBe("pc") // origin is independent of the turn pointer
  })
})

describe("line", () => {
  it("catches combatants along the axis within half-width, excluding the caster", () => {
    const s = aoeBoard()
    expect(ids(line(s, "pc", "e", 60))).toEqual(["a", "c"]) // due-east foes; `b`/`d` are off-axis
    expect(ids(line(s, "pc", "e", 30))).toEqual(["a"]) // length bounds out `c`
  })

  it("originates from any combatant and widens to catch off-axis targets", () => {
    const s = aoeBoard()
    expect(ids(line(s, "pc", "e", 60, 70))).toEqual(["a", "b", "c", "d"]) // 35 ft half-width reaches N/NE
    // From `b` at (0,30) running south, 5 ft wide: down the y-axis through the PC, missing E-side foes.
    expect(ids(line(s, "b", "s", 60))).toEqual(["pc"])
  })
})

describe("formatCaught", () => {
  it("renders egocentric lines, and a clear miss", () => {
    const s = aoeBoard()
    expect(formatCaught(s, burst(s, { distance: 0, radius: 5 }))).toBe("pc (you)")
    expect(formatCaught(s, cone(s, "pc", "s", 30))).toBe("No combatants caught.")
    expect(formatCaught(s, burst(s, { distance: 30, direction: "e", radius: 5 }))).toBe("a: 30 ft e")
  })
})
