/**
 * `submit_grade` — the benchmark grader's structured grade submission.
 *
 * The bench-only mirror of `report-findings.ts`: the grader calls this once, as its
 * final act, to score one already-flagged violation. Four string fields (all strings,
 * deliberately — the same "trivially convertible, nothing for a modest model to
 * mistype" reasoning as report_findings' boolean): `severity` and `category` are picked
 * from the rubric's labels, `rationale` is one sentence, and `duplicate_of` carries the
 * ref id of an earlier finding this one duplicates (empty string if it's fresh).
 *
 * The tool itself only acknowledges; the *signal* is the call appearing in the
 * response's tool parts, which the grade pass reads back via Backend.prompt_full →
 * Reply.tool_inputs. No prose parsing, ever — a grade that isn't a tool call is recorded
 * `ungraded`, never guessed from text.
 *
 * This is instrument, not product: it lives under `gm_llm/bench/assets/`, not the shipped
 * `gm_llm/assets/opencode/`, and is copied into the throwaway grading workspace only.
 */
export default {
  id: "gm-submit-grade",
  async setup(ctx) {
    await ctx.tool.transform((tools) => {
      tools.add({
        name: "submit_grade",
        description:
          "Submit your grade for the one flagged violation in your brief. This is your " +
          "final act — call it once. The harness reads severity, category, rationale, and " +
          "the duplicate marker from this call.",
        input: {
          type: "object",
          properties: {
            severity: {
              type: "string",
              description:
                "Exactly one of the rubric's severity labels (trivial | minor | major | " +
                "critical), by its player-facing-consequence definition.",
            },
            category: {
              type: "string",
              description:
                "Exactly one of the rubric's category labels (e.g. canon-contradiction, " +
                "spoiler-leak, agency, dice-and-uncertainty, metagame-leak, pacing, " +
                "rules-error, record-integrity), the single best fit.",
            },
            rationale: {
              type: "string",
              description: "One sentence: why this severity and this category. Terse.",
            },
            duplicate_of: {
              type: "string",
              description:
                "The ref id of an earlier finding in the window this one is the same " +
                "persisting violation as, or an empty string if it is a fresh violation.",
            },
          },
          required: ["severity", "category", "rationale", "duplicate_of"],
          additionalProperties: false,
        },
        // Called directly, not through code mode: the harness reads the call by name.
        options: { codemode: false },
        async execute() {
          return { content: "Grade submitted. The harness will record it." }
        },
      })
    })
  },
}
