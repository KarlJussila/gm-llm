import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

/**
 * A TTRPG dice expression evaluator.
 *
 * Pipeline: tokenize -> parse (recursive descent w/ precedence) -> evaluate.
 *
 * Supported syntax
 *   Arithmetic .... + - * /, unary minus, parentheses           2d6 + (1d4 - 1) * 2
 *   Dice .......... NdX (N optional), dF / df (Fate), d%         d20, 4d6, dF, d%
 *   Explode ....... !  !N  !>=N  (standard, new die each time)   3d6!  4d10!>=8
 *   Compound ...... !! (re-rolls fold into the same die)         3d6!!
 *   Penetrate ..... !p (exploded dice take -1)                   3d6!p
 *   Keep .......... kh[N] / k[N] (high), kl[N] (low)             4d6kh3, 2d20kh1
 *   Drop .......... dh[N] (high), dl[N] (low)                    4d6dl1
 *   Reroll ........ r[cmp] (recursive), ro[cmp] (once)           4d6r1, 2d20ro<3
 *   Clamp ......... mi N (minimum), ma N (maximum)               4d6mi2, 4d6ma5
 *   Success pool .. >=N >N <=N <N =N (count hits), f<N (fails)   8d10>=7, 6d6>=5f1
 *   Sort .......... s / sa (ascending), sd (descending)          4d6sd
 *   Aliases ....... adv -> 2d20kh1, dis -> 2d20kl1               adv, dis
 *
 * Counts/sides default sensibly (N -> 1) and modifiers may be combined,
 * e.g. 6d6!kh3, 4d6r1kh3, 10d10>=8!.
 */

// ---------------------------------------------------------------------------
// Limits & RNG
// ---------------------------------------------------------------------------

const MAX_COUNT = 1000
const MAX_SIDES = 10000
const REROLL_SAFETY = 100 // per-die cap on explode/reroll loops

function rollInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

// ---------------------------------------------------------------------------
// Compare points (used by explode / reroll / success / failure)
// ---------------------------------------------------------------------------

type CompareOp = "=" | "<" | ">" | "<=" | ">="
type Compare = { op: CompareOp; value: number }

function compareMatches(c: Compare, n: number): boolean {
  switch (c.op) {
    case "=":
      return n === c.value
    case "<":
      return n < c.value
    case ">":
      return n > c.value
    case "<=":
      return n <= c.value
    case ">=":
      return n >= c.value
  }
}

/** Parse an optional leading compare point, e.g. ">=8", "<3", "5". */
function takeCompare(s: string): { compare: Compare | null; rest: string } {
  const m = s.match(/^(<=|>=|<|>|=)?(\d+)/)
  if (!m) return { compare: null, rest: s }
  return {
    compare: { op: (m[1] as CompareOp) || "=", value: parseInt(m[2], 10) },
    rest: s.slice(m[0].length),
  }
}

/** Parse an optional leading integer, falling back to a default. */
function takeCount(s: string, fallback: number): { n: number; rest: string } {
  const m = s.match(/^\d+/)
  if (!m) return { n: fallback, rest: s }
  return { n: parseInt(m[0], 10), rest: s.slice(m[0].length) }
}

// ---------------------------------------------------------------------------
// Dice spec (the parsed form of an "NdX...modifiers" term)
// ---------------------------------------------------------------------------

type ExplodeKind = "standard" | "compound" | "penetrate"
type KeepDropKind = "kh" | "kl" | "dh" | "dl"

type DiceSpec = {
  notation: string // original text, for display
  count: number
  sides: number // resolved (% -> 100, F -> 1)
  fudge: boolean
  explode: { kind: ExplodeKind; compare: Compare | null } | null
  rerolls: { once: boolean; compare: Compare | null }[]
  keepDrop: { kind: KeepDropKind; count: number }[]
  clampMin: number | null
  clampMax: number | null
  success: Compare | null
  failure: Compare | null
  sort: "asc" | "desc" | null
}

function parseDiceSpec(raw: string): DiceSpec {
  const head = raw.match(/^(\d*)d(%|[fF]|\d+)(.*)$/)
  if (!head) throw new Error(`Invalid dice term: ${raw}`)

  const count = head[1] ? parseInt(head[1], 10) : 1
  const sidesRaw = head[2].toLowerCase()
  const fudge = sidesRaw === "f"
  const sides = fudge ? 1 : sidesRaw === "%" ? 100 : parseInt(sidesRaw, 10)

  if (count < 1 || count > MAX_COUNT)
    throw new Error(`Dice count must be between 1 and ${MAX_COUNT}`)
  if (!fudge && (sides < 1 || sides > MAX_SIDES))
    throw new Error(`Dice sides must be between 1 and ${MAX_SIDES}`)

  const spec: DiceSpec = {
    notation: raw,
    count,
    sides,
    fudge,
    explode: null,
    rerolls: [],
    keepDrop: [],
    clampMin: null,
    clampMax: null,
    success: null,
    failure: null,
    sort: null,
  }

  let s = head[3].toLowerCase()
  while (s.length > 0) {
    const before = s

    if (s.startsWith("!!")) {
      const { compare, rest } = takeCompare(s.slice(2))
      spec.explode = { kind: "compound", compare }
      s = rest
    } else if (s.startsWith("!p")) {
      const { compare, rest } = takeCompare(s.slice(2))
      spec.explode = { kind: "penetrate", compare }
      s = rest
    } else if (s.startsWith("!")) {
      const { compare, rest } = takeCompare(s.slice(1))
      spec.explode = { kind: "standard", compare }
      s = rest
    } else if (/^(kh|kl|dh|dl)/.test(s)) {
      const kind = s.slice(0, 2) as KeepDropKind
      const { n, rest } = takeCount(s.slice(2), 1)
      spec.keepDrop.push({ kind, count: n })
      s = rest
    } else if (s.startsWith("k")) {
      const { n, rest } = takeCount(s.slice(1), 1) // k == kh
      spec.keepDrop.push({ kind: "kh", count: n })
      s = rest
    } else if (s.startsWith("ro")) {
      const { compare, rest } = takeCompare(s.slice(2))
      spec.rerolls.push({ once: true, compare })
      s = rest
    } else if (s.startsWith("r")) {
      const { compare, rest } = takeCompare(s.slice(1))
      spec.rerolls.push({ once: false, compare })
      s = rest
    } else if (s.startsWith("sa") || s.startsWith("sd")) {
      spec.sort = s[1] === "d" ? "desc" : "asc"
      s = s.slice(2)
    } else if (s.startsWith("s")) {
      spec.sort = "asc"
      s = s.slice(1)
    } else if (s.startsWith("mi") || s.startsWith("ma")) {
      const m = s.slice(2).match(/^\d+/)
      if (!m) throw new Error(`${s.slice(0, 2)} requires a number`)
      const n = parseInt(m[0], 10)
      if (s[1] === "i") spec.clampMin = n
      else spec.clampMax = n
      s = s.slice(2 + m[0].length)
    } else if (s.startsWith("f")) {
      const { compare, rest } = takeCompare(s.slice(1))
      if (!compare) throw new Error("f (failure) requires a compare point")
      spec.failure = compare
      s = rest
    } else {
      const { compare, rest } = takeCompare(s)
      if (!compare) throw new Error(`Unknown modifier near "${s}"`)
      spec.success = compare
      s = rest
    }

    if (s === before) throw new Error(`Could not parse modifier "${s}"`)
  }

  if (spec.explode && !spec.fudge && spec.sides === 1)
    throw new Error("Cannot explode a 1-sided die")

  return spec
}

// ---------------------------------------------------------------------------
// Evaluating a dice spec into individual dice
// ---------------------------------------------------------------------------

type Die = {
  value: number
  rerolls: number[] // discarded reroll values, in order
  exploded: boolean // produced by / folded from an explosion
  dropped: boolean
  success: boolean
  failure: boolean
}

function newDie(value: number): Die {
  return {
    value,
    rerolls: [],
    exploded: false,
    dropped: false,
    success: false,
    failure: false,
  }
}

type DiceOutcome = { dice: Die[]; value: number; isPool: boolean }

function evalDice(spec: DiceSpec): DiceOutcome {
  const min = spec.fudge ? -1 : 1
  const max = spec.fudge ? 1 : spec.sides
  const roll = () => rollInt(min, max)

  const dice: Die[] = []

  const applyReroll = (die: Die) => {
    const once = spec.rerolls.filter((r) => r.once)
    const recursive = spec.rerolls.filter((r) => !r.once)
    const cmpOf = (r: { compare: Compare | null }) =>
      r.compare ?? { op: "=" as CompareOp, value: min }

    for (const r of once) {
      if (compareMatches(cmpOf(r), die.value)) {
        die.rerolls.push(die.value)
        die.value = roll()
      }
    }
    let safety = REROLL_SAFETY
    while (
      safety-- > 0 &&
      recursive.some((r) => compareMatches(cmpOf(r), die.value))
    ) {
      die.rerolls.push(die.value)
      die.value = roll()
    }
  }

  const applyClamp = (die: Die) => {
    if (spec.clampMin !== null) die.value = Math.max(die.value, spec.clampMin)
    if (spec.clampMax !== null) die.value = Math.min(die.value, spec.clampMax)
  }

  const explodeOn = spec.explode?.compare ?? { op: "=" as CompareOp, value: max }

  const explode = (base: Die) => {
    if (!spec.explode) return
    const kind = spec.explode.kind

    if (kind === "compound") {
      let safety = REROLL_SAFETY
      let last = base.value
      while (safety-- > 0 && compareMatches(explodeOn, last)) {
        last = roll()
        base.value += last
        base.exploded = true
      }
      return
    }

    // standard & penetrate add a new die for each explosion
    let safety = REROLL_SAFETY
    let trigger = base.value
    while (safety-- > 0 && compareMatches(explodeOn, trigger)) {
      const natural = roll()
      const bonus = newDie(kind === "penetrate" ? natural - 1 : natural)
      bonus.exploded = true
      dice.push(bonus)
      trigger = natural
    }
  }

  for (let i = 0; i < spec.count; i++) {
    const die = newDie(roll())
    applyReroll(die)
    applyClamp(die)
    dice.push(die)
    explode(die) // explosions checked against the final, rerolled value
  }

  applyKeepDrop(dice, spec.keepDrop)

  const kept = dice.filter((d) => !d.dropped)
  const isPool = spec.success !== null || spec.failure !== null

  let value: number
  if (isPool) {
    let successes = 0
    for (const d of kept) {
      if (spec.success && compareMatches(spec.success, d.value)) {
        d.success = true
        successes++
      }
      if (spec.failure && compareMatches(spec.failure, d.value)) {
        d.failure = true
        successes--
      }
    }
    value = successes
  } else {
    value = kept.reduce((sum, d) => sum + d.value, 0)
  }

  if (spec.sort) {
    const dir = spec.sort === "asc" ? 1 : -1
    dice.sort((a, b) => (a.value - b.value) * dir)
  }

  return { dice, value, isPool }
}

function applyKeepDrop(
  dice: Die[],
  ops: { kind: KeepDropKind; count: number }[],
): void {
  for (const op of ops) {
    const active = dice.filter((d) => !d.dropped)
    const n = Math.max(0, Math.min(op.count, active.length))
    const byValue = [...active].sort((a, b) => a.value - b.value)

    let toDrop: Die[] = []
    switch (op.kind) {
      case "kh": // keep highest n -> drop the rest from the bottom
        toDrop = byValue.slice(0, active.length - n)
        break
      case "kl": // keep lowest n -> drop the rest from the top
        toDrop = byValue.slice(n)
        break
      case "dl": // drop lowest n
        toDrop = byValue.slice(0, n)
        break
      case "dh": // drop highest n
        toDrop = byValue.slice(active.length - n)
        break
    }
    for (const d of toDrop) d.dropped = true
  }
}

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

type Token =
  | { type: "num"; value: number }
  | { type: "dice"; spec: DiceSpec }
  | { type: "op"; value: "+" | "-" | "*" | "/" }
  | { type: "lparen" }
  | { type: "rparen" }

// A dice term: optional count, "d", sides, then a run of modifier chars.
// Modifier chars stop at the arithmetic operators and parentheses.
const DICE_RE = /^\d*d(?:%|[fF]|\d+)[!a-zA-Z0-9<>=]*/
const NUM_RE = /^\d+(?:\.\d+)?/
const ALIAS: Record<string, string> = { adv: "2d20kh1", dis: "2d20kl1" }

function tokenize(input: string): Token[] {
  const tokens: Token[] = []
  let s = input.trim()

  while (s.length > 0) {
    s = s.trimStart()
    if (s.length === 0) break

    const c = s[0]
    if (c === "+" || c === "-" || c === "*" || c === "/") {
      tokens.push({ type: "op", value: c })
      s = s.slice(1)
      continue
    }
    if (c === "(") {
      tokens.push({ type: "lparen" })
      s = s.slice(1)
      continue
    }
    if (c === ")") {
      tokens.push({ type: "rparen" })
      s = s.slice(1)
      continue
    }

    const alias = s.match(/^(adv|dis)\b/i)
    if (alias) {
      tokens.push({ type: "dice", spec: parseDiceSpec(ALIAS[alias[1].toLowerCase()]) })
      s = s.slice(alias[0].length)
      continue
    }

    const dice = s.match(DICE_RE)
    if (dice) {
      tokens.push({ type: "dice", spec: parseDiceSpec(dice[0]) })
      s = s.slice(dice[0].length)
      continue
    }

    const num = s.match(NUM_RE)
    if (num) {
      tokens.push({ type: "num", value: parseFloat(num[0]) })
      s = s.slice(num[0].length)
      continue
    }

    throw new Error(`Unexpected character near "${s}"`)
  }

  if (tokens.length === 0) throw new Error("Empty expression")
  return tokens
}

// ---------------------------------------------------------------------------
// Parser (recursive descent) -> AST
// ---------------------------------------------------------------------------

type Node =
  | { type: "num"; value: number }
  | { type: "dice"; spec: DiceSpec }
  | { type: "binary"; op: "+" | "-" | "*" | "/"; left: Node; right: Node }
  | { type: "neg"; operand: Node }

function parse(tokens: Token[]): Node {
  let pos = 0
  const peek = () => tokens[pos]
  const eat = () => tokens[pos++]

  const parseExpr = (): Node => parseAdditive()

  const parseAdditive = (): Node => {
    let node = parseMultiplicative()
    let t = peek()
    while (t && t.type === "op" && (t.value === "+" || t.value === "-")) {
      eat()
      node = { type: "binary", op: t.value, left: node, right: parseMultiplicative() }
      t = peek()
    }
    return node
  }

  const parseMultiplicative = (): Node => {
    let node = parseUnary()
    let t = peek()
    while (t && t.type === "op" && (t.value === "*" || t.value === "/")) {
      eat()
      node = { type: "binary", op: t.value, left: node, right: parseUnary() }
      t = peek()
    }
    return node
  }

  const parseUnary = (): Node => {
    const t = peek()
    if (t && t.type === "op" && t.value === "-") {
      eat()
      return { type: "neg", operand: parseUnary() }
    }
    if (t && t.type === "op" && t.value === "+") {
      eat()
      return parseUnary()
    }
    return parsePrimary()
  }

  const parsePrimary = (): Node => {
    const t = peek()
    if (!t) throw new Error("Unexpected end of expression")
    if (t.type === "lparen") {
      eat()
      const node = parseExpr()
      const close = peek()
      if (!close || close.type !== "rparen")
        throw new Error("Missing closing parenthesis")
      eat()
      return node
    }
    if (t.type === "num") {
      eat()
      return { type: "num", value: t.value }
    }
    if (t.type === "dice") {
      eat()
      return { type: "dice", spec: t.spec }
    }
    throw new Error("Expected a number, dice, or '('")
  }

  const ast = parseExpr()
  if (pos !== tokens.length) throw new Error("Unexpected trailing input")
  return ast
}

// ---------------------------------------------------------------------------
// Evaluate AST, collecting a log of dice rolls for display
// ---------------------------------------------------------------------------

type DiceLogEntry = { notation: string; rolls: string; value: number; isPool: boolean }

function evaluate(node: Node, log: DiceLogEntry[]): number {
  switch (node.type) {
    case "num":
      return node.value
    case "neg":
      return -evaluate(node.operand, log)
    case "binary": {
      const a = evaluate(node.left, log)
      const b = evaluate(node.right, log)
      switch (node.op) {
        case "+":
          return a + b
        case "-":
          return a - b
        case "*":
          return a * b
        case "/":
          if (b === 0) throw new Error("Division by zero")
          return a / b
      }
      throw new Error(`Unknown operator: ${node.op}`)
    }
    case "dice": {
      const outcome = evalDice(node.spec)
      log.push({
        notation: node.spec.notation,
        rolls: renderDice(outcome.dice),
        value: outcome.value,
        isPool: outcome.isPool,
      })
      return outcome.value
    }
  }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function fmt(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100)
}

function renderDie(d: Die): string {
  let core =
    d.rerolls.length > 0
      ? `${d.rerolls.join("→")}→${d.value}`
      : String(d.value)
  if (d.exploded) core += "!"
  if (d.success) core += "✓"
  if (d.failure) core += "✗"
  if (d.dropped) core = `(${core})`
  return core
}

function renderDice(dice: Die[]): string {
  return `[${dice.map(renderDie).join(", ")}]`
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

export const DiceRollerPlugin: Plugin = async () => {
  return {
    tool: {
      dice: tool({
        description: `Roll TTRPG dice from a standard dice expression.

Arithmetic with + - * / and parentheses, e.g. (2d6 + 3) * 2.

Dice terms (NdX, N optional):
  d20, 4d6, dF (Fate/Fudge), d% (percentile)
  !        explode on max          3d6!
  !N !>=N  explode on a condition   4d10!>=8
  !!       compounding explode      3d6!!
  !p       penetrating explode      3d6!p
  kh[N] k  keep highest (def 1)     4d6kh3, adv
  kl[N]    keep lowest              2d20kl1, dis
  dh[N]    drop highest             4d6dh1
  dl[N]    drop lowest (def 1)      4d6dl1
  r[cmp]   reroll (recursive)       4d6r1, 4d6r<3
  ro[cmp]  reroll once              2d20ro1
  mi N     minimum each die         4d6mi2
  ma N     maximum each die         4d6ma5
  >=N etc  count successes (pool)   8d10>=7
  f<N      count failures           6d6>=5f1
  s/sa/sd  sort asc / desc          4d6sd

Aliases: adv -> 2d20kh1, dis -> 2d20kl1

Examples: d20+5 · 4d6dl1 · 6d6!kh3 · 2d6+1d8+3 · 8d10>=8 · (2d6+3)*2`,

        args: {
          expression: tool.schema
            .string()
            .describe("Dice expression, e.g. '4d6dl1' or '(2d6+3)*2'"),
        },

        async execute(args) {
          try {
            const ast = parse(tokenize(args.expression))
            const log: DiceLogEntry[] = []
            const total = evaluate(ast, log)

            const lines: string[] = [`🎲 ${args.expression.trim()}`]
            for (const entry of log) {
              const summary = entry.isPool
                ? `${entry.value} ${Math.abs(entry.value) === 1 ? "success" : "successes"}`
                : fmt(entry.value)
              lines.push(`  ${entry.notation} → ${entry.rolls} = ${summary}`)
            }
            lines.push(`= ${fmt(total)}`)

            const output = lines.join("\n")
            return {
              title: `🎲 ${args.expression.trim()} = ${fmt(total)}`,
              output,
              metadata: { total, rolls: log },
            }
          } catch (error: any) {
            return `Error: ${error.message}`
          }
        },
      }),
    },
  }
}
