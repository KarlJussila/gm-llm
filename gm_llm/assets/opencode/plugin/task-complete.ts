import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

/**
 * `task_complete` — the model's explicit "I have finished the process you gave me" signal.
 *
 * Why this exists: the interactive setup stages (intake + world build, character creation)
 * are multi-turn conversations with the player, and the live runner's session ends after its
 * own closing beats. The orchestrator can't tell from a returned message alone whether the
 * model is done or just paused for another exchange — and inferring it from a canon file
 * appearing on disk fires the transition mid-conversation, because those files are written
 * *during* the task, not as its final act.
 *
 * So the model tells us directly. When it has genuinely finished the process described to it —
 * intake+world done and the player confirmed, the character confirmed and all files written, or
 * the session closed out (ending proposed, feedback collected) — it calls this tool as its final
 * act. The tool itself does nothing but acknowledge; the *signal* is the call appearing in the
 * response's tool parts, which the orchestrator reads (Backend.prompt_full). The orchestrator,
 * which always knows the active phase/stage, decides what the signal means.
 *
 * Failing to call it fails safe and visibly: the stage/session simply doesn't advance and the
 * conversation continues — unlike a forgotten per-turn gate, which would silently ship unchecked
 * work. That's why a signal tool is acceptable here where the runtime gate is code-owned.
 */
export const TaskCompletePlugin: Plugin = async () => {
  return {
    tool: {
      task_complete: tool({
        description:
          "Signal that you have fully completed the process you were asked to run — and only " +
          "then. Call this as your final act once every step is done and (for player-facing " +
          "work) the player has confirmed. Calling it hands control back to the orchestrator to " +
          "move on; do not call it while you still intend to keep talking to the player.",
        args: {
          // Two channels, both optional; the brief for the task in hand says which one
          // (if any) it expects and what belongs in it.
          player_message: tool.schema
            .string()
            .optional()
            .describe(
              "The PLAYER-VISIBLE channel: a closing message the orchestrator shows to the " +
              "player verbatim, when the brief asks for one (e.g. the world-build stage's " +
              "spoiler-free world overview). Nothing spoiler-bearing, and put the real " +
              "thing here — prose you type outside the call is not surfaced."
            ),
          notes: tool.schema
            .string()
            .optional()
            .describe(
              "The INTERNAL channel: the deliverable the brief asked you to hand back to " +
              "the orchestrator, when it asks for one (e.g. the end-of-session handoff " +
              "notes). Never shown to the player, so spoilers are fine; it is filed " +
              "verbatim, so put the complete text here, not a summary of it."
            ),
        },
        async execute() {
          return "Acknowledged — completion recorded. The orchestrator will take it from here."
        },
      }),
    },
  }
}
