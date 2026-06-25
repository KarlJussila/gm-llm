import type { Plugin } from "@opencode-ai/plugin"
import { readdirSync, writeFileSync, mkdirSync, appendFileSync } from "node:fs"
import { join } from "node:path"

/**
 * Auto-captures the live play transcript so note-taking doesn't depend on the
 * model (which won't reliably write logs mid-session). Tracks the dm-runner
 * session and, on every session.idle (turn boundary), fetches the full
 * conversation from opencode and rewrites
 * `campaign/sessions/session-{N}-transcript.md`.
 *
 * The runner just plays; this records. The orchestrator's `log-extractor` then
 * turns the transcript into the structured `session-{N}.md` digest.
 *
 * Trace at /tmp/dm-transcript.log confirms it's firing — delete any time.
 */

const TRACE = "/tmp/dm-transcript.log"
function trace(s: string) {
  try {
    appendFileSync(TRACE, `${new Date().toISOString()} ${s}\n`)
  } catch {}
}

export const DmTranscriptPlugin: Plugin = async ({ client, directory }) => {
  const runnerSessions = new Set<string>()

  // Highest session-{N}-plan.md in the campaign — the session being played.
  function latestSessionNumber(): number | null {
    try {
      const files = readdirSync(join(directory, "campaign", "sessions"))
      let max = 0
      for (const f of files) {
        const m = f.match(/^session-(\d+)-plan\.md$/)
        if (m) max = Math.max(max, parseInt(m[1], 10))
      }
      return max > 0 ? max : null
    } catch {
      return null
    }
  }

  async function writeTranscript(sessionID: string) {
    try {
      const n = latestSessionNumber()
      if (n == null) return
      const res: any = await client.session.messages({
        path: { id: sessionID },
        query: { directory },
      })
      const msgs: any[] = res?.data ?? res
      if (!Array.isArray(msgs)) {
        trace(`no message array for ${sessionID}`)
        return
      }
      const lines: string[] = [`# Session ${n} — transcript (auto-captured)`, ""]
      for (const m of msgs) {
        const info = m?.info ?? m
        const parts: any[] = m?.parts ?? []
        const text = parts
          .filter((p) => p?.type === "text" && p.text)
          .map((p) => p.text)
          .join("")
          .trim()
        if (!text) continue
        lines.push(`## ${info?.role === "user" ? "Player" : "DM"}`, "", text, "")
      }
      const dir = join(directory, "campaign", "sessions")
      mkdirSync(dir, { recursive: true })
      writeFileSync(join(dir, `session-${n}-transcript.md`), lines.join("\n"))
      trace(`wrote session-${n}-transcript.md (${msgs.length} messages)`)
    } catch (e: any) {
      trace(`error: ${e?.message ?? e}`)
    }
  }

  return {
    "chat.message": async (input) => {
      if (input.agent === "dm-runner" && input.sessionID) {
        runnerSessions.add(input.sessionID)
      }
    },
    event: async ({ event }) => {
      if (
        event.type === "session.idle" &&
        runnerSessions.has(event.properties.sessionID)
      ) {
        await writeTranscript(event.properties.sessionID)
      }
    },
  }
}
