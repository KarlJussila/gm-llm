"""
The gate — run the independent checks on drafted content, in code.

The orchestrator owns it, so it runs by construction (never skipped). Each checker
submits its verdict via the `report_findings` tool (structured `report` + boolean
`passed` fields); the gate reads the tool call from the session history — no text
parsing. Live play has no gate (design/luna.md § Live play).

Every gate returns a `StageGateResult` (one verdict + its correction prompt):
`check_plan(plan)` — PRE, with the pre-loaded canon block; `check_digest(n)` /
`check_propagation(n)` — POST; and `check_init()` — INIT. The
POST/INIT checks take no preload — each is a whole-repo audit the checker reads from
disk itself, not a single draft to match names against. Each runs as a fresh session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .logs import append, banner
from .prompts import load


@dataclass
class Verdict:
    check: str   # which check produced this ("check-plan", "check-digest", …)
    passed: bool
    report: str  # full text, for the correction brief and logging
    # The checker gave no usable verdict (no tool call even after the nudge, or a
    # failure verdict with no findings anywhere) → the content passes by default.
    # Surfaced in logs/UI so a checker not doing its job never disappears silently.
    defaulted: bool = False

    @property
    def label(self) -> str:
        """Human label for logs/UI, distinguishing a real pass from a defaulted one."""
        if self.defaulted:
            return "passed (defaulted — checker gave no usable verdict)"
        return "passed" if self.passed else "violations"


@dataclass
class StageGateResult:
    """One verdict + its correction brief — every gate (plan, propagation, digest,
    init) is this shape. What varies is only which `correct-*` prompt
    the correction opens with and the report section's label; a session number formats
    into the prompt when the stage has one."""
    narrative: Verdict
    prompt: str              # correction prompt name: prompts/correct-{prompt}.md
    label: str               # section header in the correction brief ("Canon", "Digest", …)
    session: int | None = None
    canon_sections: int = 0  # only the plan gate preloads canon; 0 elsewhere

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the stage's author to fix what the check found."""
        head = load(f"correct-{self.prompt}")
        if self.session is not None:
            head = head.format(session=self.session)
        return f"{head}\n\n— {self.label} —\n" + self.narrative.report.strip()


def _parse_passed(tool_input: dict) -> bool | None:
    """The verdict from a report_findings call. `passed` is schema-typed boolean, but
    tolerate the string forms a modest model may produce. None → no usable verdict
    (the caller passes the content by default)."""
    raw = tool_input.get("passed")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
        return raw.strip().lower() == "true"
    return None


def _plan_brief(plan: str, canon: str, prologue: str = "") -> str:
    brief = load("check-plan-brief").format(plan=plan, canon=canon)
    if prologue.strip():
        brief += "\n\n--- PROLOGUE (read to the player verbatim as the session opens) ---\n" + prologue
    return brief


def _propagation_brief(n: int) -> str:
    return load("check-propagation-brief").format(n=n)


def _digest_brief(n: int) -> str:
    return load("check-digest-brief").format(n=n)


def _log_check(path, label: str, verdict: "Verdict", reply, tool_input) -> None:
    """Append the full per-check detail to `path` — the model's text, every tool
    it called, the report_findings input (if any), and the parsed verdict — so
    you can see exactly what the model said and how the gate interpreted it. This
    is the low-level per-check log (`logs.detail`), distinct from the per-turn
    summary loop/planner/reconciler write to `logs.checks`. No path → logging off.
    Best-effort: a logging failure never blocks the gate."""
    if not path:
        return
    try:
        lines = [
            banner(f"CHECK  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
                   f"label={label}  ·  passed={verdict.passed}"
                   f"{' (defaulted — no usable verdict)' if verdict.defaulted else ''}"),
        ]
        # Show every tool the model called this turn — if report_findings is
        # missing but todowrite is present, the model followed the skill's
        # task-list step but didn't (or couldn't) call the report tool. If
        # tools is empty entirely, the model called nothing at all.
        if reply.tools:
            lines.append(f"  ── TOOLS CALLED: {', '.join(sorted(reply.tools))} ──")
        else:
            lines.append("  ── TOOLS CALLED: (none — model called no tools) ──")
        lines.append("")
        if tool_input:
            lines.append(f"  ── report_findings INPUT ──")
            lines.append(f"  passed: {tool_input.get('passed', tool_input.get('verdict', '(missing)'))}")
            report = tool_input.get("report", "")
            if report:
                lines.append(f"  report ({len(report)} chars):")
                for line in report.splitlines():
                    lines.append(f"    {line}")
            else:
                lines.append("  report: (empty)")
            lines.append("")
        else:
            lines.append("  ── report_findings NOT CALLED — content passes by default ──")
            lines.append("")
        lines.append("  ── MODEL TEXT OUTPUT ──")
        for line in reply.text.splitlines():
            lines.append(f"    {line}")
        lines.append("")
        append(path, "\n".join(lines) + "\n")
    except OSError:
        pass


class Gate:
    def __init__(self, backend, preloader, logs=None):
        self.backend = backend
        self.preloader = preloader
        self.logs = logs  # None → no per-check detail logging

    def _check(self, sid: str, brief: str, label: str) -> Verdict:
        """Prompt the checker and extract the verdict from its `report_findings`
        tool call.

        The skills instruct the checker to call `report_findings` with `report`
        (findings text) and `passed` (boolean) fields as its final act — that's the
        only verdict signal. If it ends the turn without the call, `ensure_tool`
        reminds it once; if there is still no usable verdict, the content passes by
        default — a checker that didn't follow protocol has no actionable findings,
        and its stray text would be worse than nothing as a correction brief. The
        miss is stamped `defaulted` and surfaced in the log/UI, never silent.

        The checker runs a todowrite list then reports, so its findings and tool call
        can land in separate text parts — a reply reads all of them."""
        reply = self.backend.prompt_full(sid, "narrative-checker", brief)
        reply = self.backend.ensure_tool(sid, "narrative-checker", reply,
                                         tool="report_findings", args=("passed",),
                                         nudge=load("nudge-report-findings"))
        tool_input = reply.tool_inputs.get("report_findings")
        if tool_input:
            passed = _parse_passed(tool_input)
            report = str(tool_input.get("report", "")).strip()
            if passed is not None:
                # Empty-body guard: a failure verdict with no findings anywhere is
                # not actionable → passes by default. Findings the checker left in
                # its text (with an empty `report` field) still count — the Verdict
                # body falls back to reply.text below, so the correction brief has
                # something to act on.
                empty = not passed and not report and not reply.text.strip()
                if empty:
                    passed = True
                verdict = Verdict(label, passed, report or reply.text, defaulted=empty)
                _log_check(self.logs.detail if self.logs else None, label, verdict, reply, tool_input)
                return verdict
        # No usable verdict even after the reminder → the content passes by default;
        # the model's text is kept as the report so the log shows what it did instead.
        verdict = Verdict(label, passed=True, report=reply.text, defaulted=True)
        _log_check(self.logs.detail if self.logs else None, label, verdict, reply, tool_input)
        return verdict

    def _run(self, check: str, brief: str) -> Verdict:
        """Spawn a fresh checker session and run one check on it. `check` names the
        check everywhere it surfaces: the session title, the Verdict, the logs."""
        sid = self.backend.create_session(check)
        return self._check(sid, brief, check)

    def check_plan(self, plan: str, prologue: str = "") -> StageGateResult:
        """The PRE gate: narrative-only check of a draft session plan, and of session 1's
        prologue when there is one. The plan text drives the canon preload (names match by
        name)."""
        canon = self.preloader.build(plan)
        return StageGateResult(
            narrative=self._run("check-plan", _plan_brief(plan, canon, prologue)),
            prompt="plan", label="Canon",
            canon_sections=canon.count("\n### "),
        )

    def check_propagation(self, n: int) -> StageGateResult:
        """The POST gate: narrative-only check that session N's apply pass landed
        everywhere. No preload — propagation is a whole-repo audit (the digest vs.
        the updated files), not a single draft, so the checker reads on demand."""
        return StageGateResult(
            narrative=self._run("check-propagation", _propagation_brief(n)),
            prompt="propagation", label="Propagation", session=n,
        )

    def check_digest(self, n: int) -> StageGateResult:
        """The first POST gate: the digest vs. the transcript. No preload —
        source-fidelity (did the extraction keep faith with what was played), which
        the checker reads on demand, not a canon comparison."""
        return StageGateResult(
            narrative=self._run("check-digest", _digest_brief(n)),
            prompt="digest", label="Digest", session=n,
        )

    def check_init(self) -> StageGateResult:
        """The INIT gate: verify all canon written during setup against the seven-point
        checklist. No preload — the checker reads campaign/ on demand."""
        return StageGateResult(
            narrative=self._run("check-init", load("setup-gate-brief")),
            prompt="init", label="Init",
        )
