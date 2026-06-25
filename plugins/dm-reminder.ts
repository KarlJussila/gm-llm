import type { Plugin } from "@opencode-ai/plugin"
import { appendFileSync } from "node:fs"

/**
 * Keeps the session runner taking notes every turn.
 *
 * Two jobs:
 *  1. Re-inject the per-turn DM loop into the system prompt on every request —
 *     system-prompt rules decay over a long session; this keeps it fresh.
 *  2. Detect when a turn went by WITHOUT the runner writing to the session log,
 *     and escalate the reminder on the next turn. Passive reminders alone did not
 *     make note-taking stick, so this adds a consequence the model can see.
 *
 * Gated to the dm-runner agent. If its prompt's opening line is reworded, update
 * RUNNER_MARKER (otherwise the loop reminder silently stops firing). A trace is
 * appended to /tmp/dm-reminder.log so we can confirm the hook is actually firing
 * and see the per-turn logging state — delete it any time.
 *
 * State is global (this is a solo, one-session-at-a-time setup). The escalation
 * is phrased defensively ("if anything happened"), so a rare false positive is
 * harmless advice rather than a wrong instruction.
 */

const RUNNER_MARKER = "live D&D sessions with the player"
const SESSION_LOG_RE = /sessions\/session-\d+\.md/
const TRACE = "/tmp/dm-reminder.log"

function trace(line: string) {
  try {
    appendFileSync(TRACE, `${new Date().toISOString()} ${line}\n`)
  } catch {}
}

let loggedThisTurn = false
let missedLastTurn = false

const LOOP = `Per-turn DM loop — run this on EVERY player message, in order:
1. Out-of-game question (a rule, logistics, "how much longer?")? Answer it plainly and spoiler-free, then stop.
2. Otherwise the player declared what THEIR CHARACTER says or does. Never speak or act for the character. Ambiguous? Ask.
3. Uncertainty, risk, or any chance of failure (even likely)? Ask the PLAYER to roll. Do NOT announce a DC; judge privately and let a low roll fail. (Persuasion when genuinely swaying someone; ALWAYS Deception when the character lies to an NPC.)
4. Narrate the world's/NPCs' response — not the character's next move. Hand the moment back.
5. LOG IT: append to campaign/sessions/session-{N}.md what the character did, learned, met, and changed — THIS TURN, before you respond. Required every turn; a line or two is fine. A thin log is the failure we are fixing.`

export const DmReminderPlugin: Plugin = async () => {
  return {
    // A new player message is a clean per-turn boundary: did the turn that just
    // finished write to the session log?
    "chat.message": async (input) => {
      if (input.agent !== "dm-runner") return
      missedLastTurn = !loggedThisTurn
      loggedThisTurn = false
      trace(`turn boundary (missedLastTurn=${missedLastTurn})`)
    },

    // Detect the runner writing to the running session log.
    "tool.execute.after": async (input) => {
      try {
        const args = JSON.stringify((input as any).args ?? "")
        if (/write|edit|patch/i.test(input.tool) && SESSION_LOG_RE.test(args)) {
          loggedThisTurn = true
          trace(`session-log write via ${input.tool}`)
        }
      } catch {}
    },

    // Re-inject the loop each request; escalate if the last turn skipped logging.
    "experimental.chat.system.transform": async (_input, output) => {
      if (!output.system.some((s) => s.includes(RUNNER_MARKER))) return
      let msg = `<system-reminder>\n${LOOP}`
      if (missedLastTurn) {
        msg +=
          `\n\n⚠️ The session log was NOT updated on your last turn. If anything happened, append it to ` +
          `campaign/sessions/session-{N}.md NOW, before responding.`
      }
      msg += `\n</system-reminder>`
      output.system.push(msg)
      trace(`inject (missedLastTurn=${missedLastTurn})`)
    },
  }
}
