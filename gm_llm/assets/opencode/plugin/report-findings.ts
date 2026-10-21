
/**
 * `report_findings` — the checker's structured verdict submission.
 *
 * The checker calls this as its final act with two fields: `report` (the
 * findings, empty on a clean pass) and `passed` (a boolean — deliberately not
 * an enum or free string, so the schema is trivially convertible for any
 * model/provider and there is no token for a modest model to mistype).
 * The orchestrator reads the call from the session history — no text parsing.
 * The tool itself does nothing but acknowledge; the *signal* is the call
 * appearing in the response's tool parts, which the orchestrator reads
 * (Backend.prompt_full → Reply.tool_inputs).
 *
 * Modeled after `task_complete`: same "signal tool the orchestrator reads" pattern.
 */
export default {
  id: "gm-report-findings",
  async setup(ctx) {
    await ctx.tool.transform((tools) => {
      tools.add({
        name: "report_findings",
        description:
          "Submit your verification report and verdict. This is your final act — call this " +
          "once with your findings and whether the content passed. The orchestrator reads " +
          "the verdict from this call.",
        input: {
          type: "object",
          properties: {
            report: {
              type: "string",
              description:
                "Your findings. On a clean pass: empty string or 'No violations.' " +
                "On violations: a numbered list — for each finding: what's wrong, the source, " +
                "and the fix instruction. Terse and specific; this is acted on directly.",
            },
            passed: {
              type: "boolean",
              description: "true if you found no violations; false if you found any.",
            },
          },
          required: ["report", "passed"],
          additionalProperties: false,
        },
        // Called directly, not through code mode: the orchestrator reads the call by name.
        options: { codemode: false },
        async execute() {
          return { content: "Report submitted. The orchestrator will act on your verdict." }
        },
      })
    })
  },
}
