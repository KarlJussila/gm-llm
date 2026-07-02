import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

/**
 * `report_findings` — the checker's structured verdict submission.
 *
 * The checker calls this as its final act with two fields: `report` (the
 * findings, empty on a clean pass) and `verdict` ("PASS" or "VIOLATIONS").
 * The orchestrator reads the call from the session history — no text parsing.
 * The tool itself does nothing but acknowledge; the *signal* is the call
 * appearing in the response's tool parts, which the orchestrator reads
 * (Backend.prompt_full → Reply.tool_inputs).
 *
 * Modeled after `task_complete`: same "signal tool the orchestrator reads" pattern.
 */
export const ReportFindingsPlugin: Plugin = async () => {
  return {
    tool: {
      report_findings: tool({
        description:
          "Submit your verification report and verdict. This is your final act — call this " +
          "once with your findings and your verdict. The orchestrator reads the verdict from " +
          "this call.",
        args: {
          report: tool.schema
            .string()
            .describe(
              "Your findings. On a PASS: empty string or 'No violations.' " +
              "On VIOLATIONS: a numbered list — for each finding: what's wrong, the source, " +
              "and the fix instruction. Terse and specific; this is acted on directly."
            ),
          verdict: tool.schema
            .string()
            .describe(
              "PASS if you found no violations. VIOLATIONS if you found any. " +
              "Must be exactly 'PASS' or 'VIOLATIONS'."
            ),
        },
        async execute() {
          return "Report submitted. The orchestrator will act on your verdict."
        },
      }),
    },
  }
}
