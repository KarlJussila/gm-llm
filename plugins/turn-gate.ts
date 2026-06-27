import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { appendFileSync, existsSync, readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"

/**
 * The runtime turn gate as a single tool the runner calls with nothing but its
 * own narration.
 *
 * Why this exists: the built-in `task` tool's schema orders the caller to write
 * "a highly detailed task description for the agent to perform" and to "specify
 * exactly what information the agent should return". A modest model obeys that
 * at the call site no matter what its own prompt says — so it kept wrapping the
 * draft in instructions, parroting the checkers' jobs, or (worse) sending the
 * player's message instead of its narration. We can't edit that compiled schema.
 *
 * So we take the dispatch off the model. `check_turn` has one argument —
 * `narration` — and the plugin itself spawns the two checkers, authoring their
 * briefs in fixed code (correct role, correct draft, every time). The runner
 * never writes a brief; it hands over prose and gets notes back. With this in
 * place the runner has no `task` permission at all, so there's no `prompt` field
 * left for it to mis-fill.
 *
 * Trace at /tmp/turn-gate.log — delete any time.
 */

const TRACE = "/tmp/turn-gate.log"
function trace(s: string) {
  try {
    appendFileSync(TRACE, `${new Date().toISOString()} ${s}\n`)
  } catch {}
}

// Last text part of a completed subagent message, however the SDK wraps it.
function lastText(res: any): string {
  const parts: any[] = res?.data?.parts ?? res?.parts ?? []
  const texts = parts.filter((p) => p?.type === "text" && p.text).map((p) => p.text)
  return texts.length ? texts[texts.length - 1].trim() : ""
}

// Human-readable record of every gate: the narration checked and both verdicts.
// Lets a person (or the autoplay harness) watch what the checkers actually said,
// which the runner never surfaces. Separate from the terse timing trace.
const CHECKS = "/tmp/turn-gate-checks.log"
function logChecks(sessionID: string, narration: string, canon: string, conduct: string) {
  try {
    const block = [
      `\n${"=".repeat(72)}`,
      `check @ ${new Date().toISOString()} | session ${sessionID}`,
      "-".repeat(72),
      "NARRATION:",
      narration,
      "",
      "CANON (narrative-checker):",
      canon,
      "",
      "CONDUCT (rules-checker):",
      conduct,
      "",
    ].join("\n")
    appendFileSync(CHECKS, block)
  } catch {}
}

export const TurnGatePlugin: Plugin = async ({ client, directory }) => {
  // What the player said this turn. The transcript file is written only at turn
  // boundaries (session.idle), so mid-turn — exactly when check_turn runs — it
  // does NOT yet contain this message. Without it the checkers judge the draft
  // blind and flag faithful renderings of what the player said as "acting for
  // the character." So we read it live from the session, the way dm-transcript
  // does.
  async function latestPlayerMessage(sessionID: string): Promise<string> {
    try {
      const res: any = await client.session.messages({
        path: { id: sessionID },
        query: { directory },
      })
      const msgs: any[] = res?.data ?? res
      if (!Array.isArray(msgs)) return ""
      for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i]
        const info = m?.info ?? m
        if (info?.role !== "user") continue
        const text = (m?.parts ?? [])
          .filter((p: any) => p?.type === "text" && p.text)
          .map((p: any) => p.text)
          .join("")
          .trim()
        if (text) return text
      }
      return ""
    } catch (e: any) {
      trace(`latestPlayerMessage error: ${e?.message ?? e}`)
      return ""
    }
  }

  // --- Canon preload (narrative-checker only) -----------------------------
  // The narrative-checker's latency is dominated by sequential file-read
  // round-trips: it reads a fixed baseline plus the entity files the draft
  // touches, one model turn each. We do those reads here instead — fast, local,
  // deterministic — and hand the checker the text up front. Draft-specific
  // matching is heuristic (entity names against INDEX), so the block is framed
  // as an incomplete head start: the checker still resolves and reads anything
  // it's missing (see the check-turn skill).

  const CAMPAIGN = join(directory, "campaign")

  function readRel(rel: string): string | null {
    try {
      const p = join(CAMPAIGN, rel)
      return existsSync(p) ? readFileSync(p, "utf8") : null
    } catch {
      return null
    }
  }

  function listRel(subdir: string, re: RegExp): string[] {
    try {
      return readdirSync(join(CAMPAIGN, subdir))
        .filter((f) => re.test(f))
        .map((f) => `${subdir}/${f}`)
    } catch {
      return []
    }
  }

  // Highest session-{N}-plan.md — the session being played.
  function latestSessionNumber(): number | null {
    let max = 0
    for (const f of listRel("sessions", /^session-\d+-plan\.md$/)) {
      const m = f.match(/session-(\d+)-plan\.md$/)
      if (m) max = Math.max(max, parseInt(m[1], 10))
    }
    return max > 0 ? max : null
  }

  type IndexEntry = { name: string; info: string | null; state: string | null }

  // Parse the INDEX.md markdown tables into entity rows. Columns are
  // | slug | name | status | info|design | state | one-line |.
  function parseIndex(text: string): IndexEntry[] {
    const out: IndexEntry[] = []
    const isPath = (s: string) => !!s && s !== "—" && /\.md$/.test(s)
    for (const line of text.split("\n")) {
      if (!line.trimStart().startsWith("|")) continue
      const c = line.split("|").map((x) => x.trim())
      const cols = c.slice(1, c.length - 1) // drop the empty edges
      if (cols.length < 5) continue
      const [slug, name, , info, state] = cols
      if (!slug || slug === "slug" || slug.startsWith("-")) continue // header/separator
      out.push({ name, info: isPath(info) ? info : null, state: isPath(state) ? state : null })
    }
    return out
  }

  function escapeRe(s: string): string {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  }

  // Match an entity by its full name and by distinctive name-words (>= 4
  // chars), so "Magren" hits "Magren Soley". Liberal: a false match only
  // preloads one extra small file, never drops correctness.
  function nameMatches(name: string, hay: string): boolean {
    const base = name.replace(/^the\s+/i, "").trim()
    const terms = new Set<string>([base])
    for (const tok of base.split(/[\s'-]+/)) if (tok.length >= 4) terms.add(tok)
    for (const t of terms) {
      if (!t) continue
      if (new RegExp(`\\b${escapeRe(t.toLowerCase())}\\b`).test(hay)) return true
    }
    return false
  }

  function tailChars(text: string, n: number): string {
    return text.length <= n ? text : "…\n" + text.slice(text.length - n)
  }

  // Build the canon block: always-needed baseline + entity files the draft
  // names + a tail of the transcript. Returns "" if nothing could be read.
  function canonPreload(draft: string): string {
    const n = latestSessionNumber()
    const indexText = readRel("INDEX.md") ?? ""
    const hay = draft.toLowerCase()
    const matched: string[] = []
    for (const e of parseIndex(indexText)) {
      if (!nameMatches(e.name, hay)) continue
      if (e.info) matched.push(e.info)
      if (e.state) matched.push(e.state)
    }

    const baseline = [
      "INDEX.md",
      "state/current.md",
      ...listRel("characters", /\.knowledge\.md$/),
      ...listRel("arcs", /\.md$/),
      ...(n ? [`sessions/session-${n}-deltas.md`] : []),
    ]

    const seen = new Set<string>()
    const sections: string[] = []
    for (const rel of [...baseline, ...matched]) {
      if (seen.has(rel)) continue
      seen.add(rel)
      const body = readRel(rel)
      if (body == null) continue
      sections.push(`### ${rel}\n${body.trim()}`)
    }
    if (n) {
      const t = readRel(`sessions/session-${n}-transcript.md`)
      if (t) sections.push(`### sessions/session-${n}-transcript.md (recent tail)\n${tailChars(t, 4000)}`)
    }
    trace(`canon preload: ${sections.length} sections`)
    if (!sections.length) return ""
    return (
      "--- PRE-LOADED CANON — already read for you; do NOT re-read these ---\n" +
      "Each `### <path>` block below is the FULL current contents of that file, read for you now. " +
      "The list of `### ` paths is exactly what is already loaded. Before you call any read or grep " +
      "tool, check that list: if a file appears below, use its text from here — do not re-open it. " +
      "Use a read tool ONLY for a file the draft references that does NOT appear below. (The set is " +
      "matched to the draft by name and can miss an entity named only indirectly or by epithet; " +
      "resolve those against the INDEX block below and read just those few.)\n\n" +
      sections.join("\n\n") +
      "\n\n--- end pre-loaded canon ---\n\n"
    )
  }

  // Spawn one checker as a child of the runner's session, hand it a
  // plugin-authored brief, and return its final text. Briefs are fixed here so
  // the runner never authors one.
  async function runChecker(
    parentID: string,
    agent: string,
    title: string,
    brief: string,
  ): Promise<string> {
    try {
      trace(`${agent}: start`)
      const created: any = await client.session.create({
        body: { parentID, title },
        query: { directory },
      })
      const id = created?.data?.id ?? created?.id
      if (!id) {
        trace(`${agent}: no session id from create`)
        return `[${agent} could not start]`
      }
      const res: any = await client.session.prompt({
        path: { id },
        query: { directory },
        body: { agent, parts: [{ type: "text", text: brief }] },
      })
      const out = lastText(res)
      trace(`${agent}: ${out.length} chars`)
      return out || `[${agent} returned nothing]`
    } catch (e: any) {
      trace(`${agent} error: ${e?.message ?? e}`)
      return `[${agent} error: ${e?.message ?? e}]`
    }
  }

  return {
    tool: {
      check_turn: tool({
        description:
          "Check the narration you wrote for the current turn before the player sees it. " +
          "Pass your narration as `narration`; this returns notes from the canon and conduct " +
          "checks. Call it once per turn, before you send anything to the player: apply whatever " +
          "the checks raise and send — do not call it again for the same turn.",
        args: {
          narration: tool.schema
            .string()
            .describe(
              "Your finished narration for this turn — the exact prose the player will read, " +
                "and nothing else. Not the player's message; not any note or instruction about it.",
            ),
        },
        execute: async (args, context) => {
          const narration = (args.narration ?? "").trim()
          if (!narration) {
            return "[no narration supplied — pass the prose you wrote for this turn as `narration`]"
          }

          const parent = context.sessionID

          // What the player said this turn — the most important context for
          // judging whether the draft renders what the player said or invents
          // beyond it. Supplied here so the checkers don't depend on the
          // (mid-turn stale) transcript file for it.
          const playerMsg = await latestPlayerMessage(parent)
          const playerContext = playerMsg
            ? "--- PLAYER'S LATEST MESSAGE (what the player said this turn) ---\n" +
              playerMsg +
              "\n\n"
            : ""

          // Briefs are authored here, not by the model: correct role, correct
          // draft, the player's real words, every call. The narrative brief also
          // carries pre-read canon (see canonPreload); the rules-checker is
          // canon-free, so its brief stays lean.
          const canon = canonPreload(narration)
          const narrativeBrief =
            "Role: check-turn. Verify the runner's drafted turn per your check-turn skill. The " +
            "player's latest message below is what the player said this turn; the drafted turn " +
            "is the narration about to be sent in response.\n\n" +
            playerContext +
            canon +
            "--- DRAFTED TURN ---\n" +
            narration
          const conductBrief =
            "Check the runner's drafted turn for conduct violations. The player's latest message " +
            "below is what the player said this turn; the drafted turn is the narration about to " +
            "be sent in response.\n\n" +
            playerContext +
            "--- DRAFTED TURN ---\n" +
            narration

          const [narrativeOut, conductOut] = await Promise.all([
            runChecker(parent, "narrative-checker", "check-turn", narrativeBrief),
            runChecker(parent, "rules-checker", "rules-check", conductBrief),
          ])
          logChecks(parent, narration, narrativeOut, conductOut)

          return [
            "Two independent checks ran on your narration. Apply every fix in one pass, then send",
            "the corrected narration to the player. Do not call `check_turn` again for this turn.",
            "",
            "=== CANON (narrative-checker) ===",
            narrativeOut,
            "",
            "=== CONDUCT (rules-checker) ===",
            conductOut,
          ].join("\n")
        },
      }),
    },
  }
}
