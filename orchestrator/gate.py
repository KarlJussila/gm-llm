"""
The gate — run the independent checks on drafted content, in code.

This is what the runner (and the dm, at planning) used to invoke as a tool; now the
orchestrator owns it, so it runs by construction (never skipped). Each checker
submits its verdict via the `report_findings` tool (structured `report` + `verdict`
fields); the gate reads the tool call from the session history — no text parsing.

Three shapes share one spawn-and-check engine:
  - `check(narration, player_msg)` — the RUNTIME gate. One narrative-checker
    session does both jobs, warm: first `check-turn` (canon coherence, with the
    pre-loaded canon block), then `check-conduct` (table-craft conduct) on the
    **same session** — so the canon/ledger context the canon check just loaded
    is available when judging conduct (e.g. a PC knowledge leak). The orchestrator
    supplies the player's message directly — it owns the loop, so nothing has to
    fetch it from a transcript.
  - `check_plan(plan)` — the PRE gate: narrative-checker, `check-plan` only (a plan
    has no conduct to police and no player message), with the pre-loaded canon block.
  - `check_propagation(n)` — the POST gate: narrative-checker, `check-propagation`
    only, verifying that session N's updates landed in canon and state. No preload —
    the checker reads N's digest against the updated files itself; there's no single
    draft to match names against.

The runtime gate reuses one session for both checks (warm context, one fewer
spawn); every other gate runs as a fresh session per call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .logs import append, banner
from .prompts import load


@dataclass
class Verdict:
    agent: str
    passed: bool
    report: str  # full text, for the correction brief and logging
    empty_violation: bool = False  # stamped VIOLATIONS with no findings → downgraded to pass

    @property
    def label(self) -> str:
        """Human label for logs/UI, distinguishing a real pass from a downgraded one."""
        if self.empty_violation:
            return "PASS (empty VIOLATIONS — checker gave no findings)"
        return "PASS" if self.passed else "VIOLATIONS"


@dataclass
class GateResult:
    narrative: Verdict
    conduct: Verdict
    player_msg: str
    canon_sections: int

    @property
    def violations(self) -> bool:
        return not (self.narrative.passed and self.conduct.passed)

    def correction_brief(self) -> str:
        """The message handed back to the runner to revise its narration."""
        parts = [load("correct-turn") + "\n"]
        if not self.narrative.passed:
            parts.append("— Canon —\n" + self.narrative.report.strip())
        if not self.conduct.passed:
            parts.append("— Conduct —\n" + self.conduct.report.strip())
        return "\n\n".join(parts)


@dataclass
class PlanGateResult:
    narrative: Verdict
    canon_sections: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the dm to revise the plan file it just wrote."""
        return load("correct-plan") + "\n\n— Canon —\n" + self.narrative.report.strip()


@dataclass
class PropagationGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the dm to backfill the gaps from its apply pass."""
        return (load("correct-propagation").format(session=self.session)
                + "\n\n— Propagation —\n" + self.narrative.report.strip())


@dataclass
class DigestGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the digest's author (log-extractor) to fix it."""
        return (load("correct-digest").format(session=self.session)
                + "\n\n— Digest —\n" + self.narrative.report.strip())


@dataclass
class FeedbackGateResult:
    narrative: Verdict
    session: int

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the feedback curator (analyst) to fix the files."""
        return (load("correct-feedback").format(session=self.session)
                + "\n\n— Feedback —\n" + self.narrative.report.strip())


@dataclass
class InitGateResult:
    narrative: Verdict

    @property
    def violations(self) -> bool:
        return not self.narrative.passed

    def correction_brief(self) -> str:
        """The message handed back to the dm to fix init canon issues."""
        return load("correct-init") + "\n\n— Init —\n" + self.narrative.report.strip()


def _narrative_brief(player_msg: str, canon: str, narration: str) -> str:
    return load("check-turn-brief").format(player_msg=player_msg, canon=canon, narration=narration)


def _conduct_brief(player_msg: str, narration: str) -> str:
    return load("check-conduct-brief").format(player_msg=player_msg, narration=narration)


def _plan_brief(plan: str, canon: str) -> str:
    return load("check-plan-brief").format(plan=plan, canon=canon)


def _propagation_brief(n: int) -> str:
    return load("check-propagation-brief").format(n=n)


def _digest_brief(n: int) -> str:
    return load("check-digest-brief").format(n=n)


def _feedback_brief(n: int) -> str:
    return load("check-feedback-brief").format(n=n)


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
                   f"label={label}  ·  verdict={'PASS' if verdict.passed else 'VIOLATIONS'}"
                   f"{' (empty-violation downgraded)' if verdict.empty_violation else ''}"),
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
            lines.append(f"  verdict: {tool_input.get('verdict', '(missing)')}")
            report = tool_input.get("report", "")
            if report:
                lines.append(f"  report ({len(report)} chars):")
                for line in report.splitlines():
                    lines.append(f"    {line}")
            else:
                lines.append("  report: (empty)")
            lines.append("")
        else:
            lines.append("  ── report_findings NOT CALLED — fail-safe to VIOLATIONS ──")
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
        (findings text) and `verdict` ("PASS" / "VIOLATIONS") fields as its final
        act — that's the only verdict signal. If the model didn't call the tool
        (or called it without a usable verdict field), fail-safe to VIOLATIONS
        with the model's text as the report body, so the checker's output still
        reaches the caller rather than slipping by silently.

        `whole=True`: a checker runs a todowrite list then reports, so its findings
        and tool call can land in separate text parts — we need all of them."""
        reply = self.backend.prompt_full(sid, "narrative-checker", brief, whole=True)
        tool_input = reply.tool_inputs.get("report_findings")
        if tool_input:
            verdict_str = str(tool_input.get("verdict", "")).upper().strip()
            report = str(tool_input.get("report", "")).strip()
            if verdict_str in ("PASS", "VIOLATIONS"):
                passed = verdict_str == "PASS"
                # Empty-body guard: VIOLATIONS with no findings → not actionable → pass.
                empty = not passed and not report
                if empty:
                    passed = True
                verdict = Verdict(label, passed, report or reply.text, empty_violation=empty)
                _log_check(self.logs.detail if self.logs else None, label, verdict, reply, tool_input)
                return verdict
        # No usable tool call → fail-safe to VIOLATIONS (the model didn't follow
        # the skill; surface its text so the caller can see what went wrong).
        verdict = Verdict(label, passed=False, report=reply.text)
        _log_check(self.logs.detail if self.logs else None, label, verdict, reply, tool_input)
        return verdict

    def _run(self, title: str, brief: str, label: str) -> Verdict:
        """Spawn a fresh checker session and run one check on it."""
        sid = self.backend.create_session(title)
        return self._check(sid, brief, label)

    def check(self, narration: str, player_msg: str) -> GateResult:
        """The RUNTIME gate. One narrative-checker session, two checks, warm:
        first `check-turn` (canon coherence), then `check-conduct` (table-craft
        conduct) on the same session — so the conduct check benefits from the
        canon/ledger context the canon check just loaded. The two verdicts stay
        separate (the correction brief and the UI both distinguish canon vs.
        conduct); the model context is shared."""
        canon = self.preloader.build(narration)
        sid = self.backend.create_session("check-turn")
        narrative = self._check(sid, _narrative_brief(player_msg, canon, narration),
                                "narrative-checker")
        conduct = self._check(sid, _conduct_brief(player_msg, narration),
                              "check-conduct")
        return GateResult(
            narrative=narrative,
            conduct=conduct,
            player_msg=player_msg,
            canon_sections=canon.count("\n### "),
        )

    def check_plan(self, plan: str) -> PlanGateResult:
        """The PRE gate: narrative-only check of a draft session plan. The plan text
        drives the canon preload exactly as a draft turn does (names match by name)."""
        canon = self.preloader.build(plan)
        return PlanGateResult(
            narrative=self._run("check-plan", _plan_brief(plan, canon), "narrative-checker"),
            canon_sections=canon.count("\n### "),
        )

    def check_propagation(self, n: int) -> PropagationGateResult:
        """The POST gate: narrative-only check that session N's apply pass landed
        everywhere. No preload — propagation is a whole-repo audit (the digest vs.
        the updated files), not a single draft, so the checker reads on demand."""
        return PropagationGateResult(
            narrative=self._run("check-propagation", _propagation_brief(n), "narrative-checker"),
            session=n,
        )

    def check_digest(self, n: int) -> DigestGateResult:
        """The first POST gate: the digest vs. the transcript. No preload —
        source-fidelity (did the extraction keep faith with what was played), which
        the checker reads on demand, not a canon comparison."""
        return DigestGateResult(
            narrative=self._run("check-digest", _digest_brief(n), "narrative-checker"),
            session=n,
        )

    def check_feedback(self, n: int) -> FeedbackGateResult:
        """A POST gate: the curated feedback files vs. the player's actual words. No
        preload — the checker reads the digest's feedback section and the feedback
        files on demand."""
        return FeedbackGateResult(
            narrative=self._run("check-feedback", _feedback_brief(n), "narrative-checker"),
            session=n,
        )

    def check_init(self) -> InitGateResult:
        """The INIT gate: verify all canon written during setup against the seven-point
        checklist. No preload — the checker reads campaign/ on demand."""
        return InitGateResult(
            narrative=self._run("check-init", load("setup-gate-brief"), "narrative-checker"),
        )
