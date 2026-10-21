/**
 * `submit_checks` — the after-play checker's findings for one turn (design/benchmark.md § Check).
 *
 * Called once per turn with a list of findings, empty when the turn is clean. The tool only
 * acknowledges; `bench check` reads the call back from the session's tool parts, never from
 * prose. Instrument, not product: it lives under `gm_llm/bench/assets/` and is copied into the
 * check workspace only.
 */
export default {
  id: "gm-submit-checks",
  async setup(ctx) {
    await ctx.tool.transform((tools) => {
      tools.add({
        name: "submit_checks",
        description:
          "Submit this turn's findings — an empty list if the turn is clean. Call it once per turn.",
        input: {
          type: "object",
          properties: {
            findings: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  check: { type: "string", description: "canon, conduct or combat." },
                  claim: { type: "string", description: "What the DM got wrong, in one sentence." },
                  evidence: {
                    type: "string",
                    description: "A quote from the turn, the file, or the earlier turn that shows it.",
                  },
                  category: { type: "string", description: "The best-fitting category label." },
                  continues: {
                    type: "string",
                    description:
                      "The ref of an earlier finding this one carries on (e.g. s3t5#1), or an empty string.",
                  },
                },
                required: ["check", "claim", "evidence", "category", "continues"],
                additionalProperties: false,
              },
            },
          },
          required: ["findings"],
          additionalProperties: false,
        },
        // Called directly, not through code mode: the harness reads the call by name.
        options: { codemode: false },
        async execute() {
          return { content: "Findings recorded for this turn." }
        },
      })
    })
  },
}
