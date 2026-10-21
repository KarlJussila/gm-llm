/**
 * `submit_grade` — the grader's verdict on one finding (design/benchmark.md § Grade).
 *
 * The tool only acknowledges; `bench grade` reads the call back from the session's tool parts,
 * never from prose. Instrument, not product: it lives under `gm_llm/bench/assets/` and is copied
 * into the grading workspace only.
 */
export default {
  id: "gm-submit-grade",
  async setup(ctx) {
    await ctx.tool.transform((tools) => {
      tools.add({
        name: "submit_grade",
        description: "Submit your verdict on the finding in the last message. Call it once per finding.",
        input: {
          type: "object",
          properties: {
            verdict: { type: "string", description: "confirmed or rejected." },
            severity: {
              type: "string",
              description: "trivial, minor, major or critical. Empty when rejected.",
            },
            category: {
              type: "string",
              description: "The rubric's category that fits best. Empty when rejected.",
            },
            rationale: { type: "string", description: "One sentence: why." },
            duplicate_of: {
              type: "string",
              description:
                "The ref of an earlier confirmed finding this is the same violation as, or an empty string.",
            },
          },
          required: ["verdict", "severity", "category", "rationale", "duplicate_of"],
          additionalProperties: false,
        },
        // Called directly, not through code mode: the harness reads the call by name.
        options: { codemode: false },
        async execute() {
          return { content: "Grade recorded." }
        },
      })
    })
  },
}
