
/**
 * `task_complete` — the model's explicit "I have finished the stage you gave me" signal.
 *
 * Why this exists: the interactive setup stages (intake + world build, character creation)
 * are multi-turn conversations with the player, and the live runner's session ends after its
 * own closing beats. The orchestrator can't tell from a returned message alone whether the
 * model is done or just paused for another exchange — and inferring it from a canon file
 * appearing on disk fires the transition mid-conversation, because those files are written
 * *during* the task, not as its final act.
 *
 * So the model tells us directly. What "the stage is done" means — what has to be written and
 * confirmed — is the brief's business, felt one stage at a time; this tool only reports that
 * the brief's conditions hold. The tool itself does nothing but acknowledge; the *signal* is
 * the call appearing in the response's tool parts, which the orchestrator reads
 * (Backend.prompt_full). The orchestrator, which always knows the active phase/stage, decides
 * what the signal means.
 *
 * Failing to call it fails safe and visibly: the stage/session simply doesn't advance and the
 * conversation continues.
 */
export default {
  id: "gm-task-complete",
  async setup(ctx) {
    await ctx.tool.transform((tools) => {
      tools.add({
        name: "task_complete",
        description:
                "Signal completion of the current stage, called as and when instructed.",
        input: {
          type: "object",
          properties: {
            notes: {
              type: "string",
              description:
                "Closing notes for the task — only when the task asks for them.",
            },
          },
          additionalProperties: false,
        },
        // Called directly, not through code mode: the orchestrator reads the call by name.
        options: { codemode: false },
        async execute() {
          return { content: "Acknowledged — completion recorded. The orchestrator will take it from here." }
        },
      })
    })
  },
}
