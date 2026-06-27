import type { Plugin } from "@opencode-ai/plugin"

/**
 * Re-injects the per-turn DM *craft* loop into the system prompt on every
 * request while the session runner is active — system-prompt rules decay over a
 * long session, so this keeps the craft fresh. (Note-taking is no longer in this
 * loop: the transcript is captured automatically by dm-transcript.ts.)
 *
 * Gated to the dm-runner agent via a stable phrase from its prompt. If that
 * opening line is reworded, update RUNNER_MARKER or the reminder stops firing.
 */

const RUNNER_MARKER = "live D&D sessions with the player"

const LOOP = `<system-reminder>
Per-turn DM craft — run this on EVERY player message, in order:
1. Out-of-game question (a rule, logistics, "how much longer?")? Answer it plainly and spoiler-free, then stop.
2. Otherwise the player declared what THEIR CHARACTER says or does. Never speak or act for the character — no dialogue in their voice, no deciding what they do next. Ambiguous? Ask. If they overstep (narrating an NPC/the world, or an ability the character plainly lacks), step out of game and say so — don't play it as done.
3. Uncertainty, risk, or any chance of failure (even likely)? Ask the PLAYER to roll. Do NOT announce a DC; judge privately and let a low roll fail. (Persuasion when genuinely swaying someone; ALWAYS Deception when the character lies to an NPC.)
4. Write the world's/NPCs' response — not the character's next move — as your reply.
</system-reminder>`

export const DmReminderPlugin: Plugin = async () => {
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (output.system.some((s) => s.includes(RUNNER_MARKER))) {
        output.system.push(LOOP)
      }
    },
  }
}
