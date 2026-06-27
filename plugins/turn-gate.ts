import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { appendFileSync } from "node:fs"

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
          // draft, the player's real words, every call. The checkers find any
          // further context (earlier scenes, canon) from disk.
          const narrativeBrief =
            "Role: check-turn. Verify the runner's drafted turn per your check-turn skill. The " +
            "player's latest message below is what the player said this turn; the drafted turn " +
            "is the narration about to be sent in response.\n\n" +
            playerContext +
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
