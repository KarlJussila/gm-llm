import type { Plugin } from "@opencode-ai/plugin"

/**
 * Re-injects the per-turn DM loop into the system prompt on every request while
 * the session runner is active. System-prompt rules decay over a long session;
 * this keeps the loop fresh every turn so the runner doesn't drift off it.
 *
 * Gated to the dm-runner agent by detecting a stable phrase from its prompt
 * (`live D&D sessions with the player`). If that opening line is reworded, update
 * RUNNER_MARKER to match — otherwise the reminder silently stops firing.
 */

const RUNNER_MARKER = "live D&D sessions with the player"

const TURN_REMINDER = `<system-reminder>
Per-turn DM loop — run this on EVERY player message, in order:
1. Out-of-game question (a rule, logistics, "how much longer?")? Answer it plainly and spoiler-free, then stop — do not advance the fiction.
2. Otherwise the player has declared what THEIR CHARACTER says or does. Never speak or act for the character — no dialogue in their voice, no deciding what they do next. If the action is ambiguous, ask; don't assume.
3. Uncertainty, risk, or any chance of failure (even a likely success)? Ask the PLAYER to roll the fitting check. Do NOT announce a DC; judge the result privately and let a low roll fail or complicate.
4. Narrate what happens — the world's and NPCs' response to the action and roll — not the character's next move. Hand the moment back to the player.
5. Capture NOW, before the next exchange: if the character learned something or anything of consequence happened, update the knowledge ledger (+flags), world/item/document files, and the running session log. Doing it "later" does not happen.
</system-reminder>`

export const DmReminderPlugin: Plugin = async () => {
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      const isRunner = output.system.some((s) => s.includes(RUNNER_MARKER))
      if (isRunner) output.system.push(TURN_REMINDER)
    },
  }
}
