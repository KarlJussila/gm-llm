"""
The per-turn loop — the heart of the pivot.

The orchestrator, not the model, drives every turn: the runner drafts, the gate
ALWAYS runs, and on violations the runner gets exactly ONE bounded correction pass
before the result is returned. No tool the model can forget to call; no re-check
loop; nothing reaches the player (or the benchmark's scorer) until the loop says so.

`Game` is the headless core. Interfaces (the TUI, the benchmark) drive it:
  g = Game(backend, gate)
  g.start()                 # runner opens the scene (gated)
  g.turn(player_input)      # one full gated turn -> TurnResult
  g.meta(question)          # out-of-game question, answered ungated
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class TurnResult:
    player_input: str
    draft: str          # the runner's first draft
    final: str          # what reaches the player (== draft unless corrected)
    gate: "GateResult"  # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool


class Game:
    def __init__(self, backend, gate, runner_agent: str = "dm-runner",
                 on_turn=None, checks_log: str | None = None):
        self.backend = backend
        self.gate = gate
        self.runner_agent = runner_agent
        self.on_turn = on_turn
        self.checks_log = checks_log
        self.runner_sid = backend.create_session("dm-runner game")

    def start(self, kickoff: str = "Let's begin the session.") -> TurnResult:
        """The opening scene — gated like any turn (it's player-facing narration)."""
        return self._gated_turn(kickoff, kickoff)

    def turn(self, player_input: str) -> TurnResult:
        return self._gated_turn(player_input, player_input)

    def meta(self, question: str) -> str:
        """An out-of-game question. The runner answers it (spoiler-free, per its
        prompt); the orchestrator does NOT gate it — it isn't narration."""
        return self.backend.prompt(self.runner_sid, self.runner_agent, question)

    def _gated_turn(self, message: str, player_msg: str) -> TurnResult:
        draft = self.backend.prompt(self.runner_sid, self.runner_agent, message)
        result = self.gate.check(draft, player_msg)
        final, corrected = draft, False
        if result.violations:
            # Exactly one correction pass. We do NOT re-gate the revision — bounded
            # by construction; if it's still imperfect it goes out and the log shows it.
            final = self.backend.prompt(self.runner_sid, self.runner_agent, result.correction_brief())
            corrected = True
        tr = TurnResult(player_msg, draft, final, result, corrected)
        self._log(tr)
        if self.on_turn:
            self.on_turn(tr)
        return tr

    def _log(self, tr: TurnResult) -> None:
        if not self.checks_log:
            return
        try:
            with open(self.checks_log, "a") as f:
                f.write(_format_block(tr))
        except OSError:
            pass


def _sec(label: str, body: str) -> str:
    return f"\n  ── {label} {'─' * max(0, 68 - len(label))}\n\n{(body or '').strip()}\n"


def _format_block(tr: TurnResult) -> str:
    bar = "█" * 74
    g = tr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    cv = "PASS" if g.conduct.passed else "VIOLATIONS"
    blocks = [
        "", bar,
        f"  TURN  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
        f"{'CORRECTED' if tr.corrected else 'clean'}  ·  canon {g.canon_sections} sections",
        bar,
        _sec("PLAYER", tr.player_input),
        _sec(f"CANON · {nv}", g.narrative.report),
        _sec(f"CONDUCT · {cv}", g.conduct.report),
    ]
    if tr.corrected:
        blocks.append(_sec("DRAFT (pre-correction)", tr.draft))
    blocks.append(_sec("FINAL NARRATION", tr.final))
    blocks.append("")
    return "\n\n".join(blocks)
