"""
Init — the orchestrated new-campaign flow.

Init is the one phase that isn't an autonomous dispatch: `campaign-setup` is a guided
conversation with the player (intake, character, hooks) interleaved with authoring. So
`Setup` mirrors `Game`'s conversational shape rather than `Reconciler`'s staged pipeline
— the dm runs `campaign-setup` in one thread, and the orchestrator just provides the
surface and owns the edges.

  s = Setup(backend, gate, directory)
  s.start()                 # the dm loads campaign-setup, opens with the intake question
  s.turn(player_input)      # one conversational exchange -> SetupTurn{reply, done}
  s.finalize()              # once done: plan session 1 (code-gated) -> returns 1

Completion is read from git/disk — `campaign: init` committed — never by parsing the
dm's prose. The session-1 plan is the one gateable artifact at init, so the orchestrator
owns it via the existing `Planner` (reusing the warm setup thread).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .planner import Planner
from .prompts import load


@dataclass
class SetupTurn:
    reply: str   # the dm's message to the player this exchange
    done: bool   # True once `campaign: init` is committed — time to finalize


class Setup:
    """Drives the dm through `campaign-setup` as a player-facing conversation."""

    def __init__(self, backend, gate, directory: str, dm_agent: str = "dm",
                 on_prep=None, checks_log: str | None = None):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.dm_agent = dm_agent
        self.on_prep = on_prep
        self.checks_log = checks_log
        self.root = Path(directory)
        self.dm_sid = backend.create_session("dm setup")

    def start(self) -> SetupTurn:
        reply = self.backend.prompt(self.dm_sid, self.dm_agent, load("setup-kickoff"))
        return SetupTurn(reply, self._init_committed())

    def turn(self, player_input: str) -> SetupTurn:
        reply = self.backend.prompt(self.dm_sid, self.dm_agent, player_input)
        return SetupTurn(reply, self._init_committed())

    def finalize(self) -> int:
        """Once init is committed, plan session 1 — the dm authors in the warm setup
        thread, code gates `check-plan` and commits — then return the new session (1)."""
        Planner(self.backend, self.gate, dm_agent=self.dm_agent, dm_sid=self.dm_sid,
                on_prep=self.on_prep, checks_log=self.checks_log).prep_session(1, commit=True)
        return 1

    def _init_committed(self) -> bool:
        """Done iff `campaign: init` is in the campaign repo's history (or session 1 is
        already planned). A robust file/git signal — we never prose-parse the dm."""
        if (self.root / "campaign" / "sessions" / "session-1-plan.md").is_file():
            return True
        try:
            log = subprocess.run(["git", "log", "--pretty=%s"], cwd=self.root,
                                 capture_output=True, text=True)
        except OSError:
            return False
        return log.returncode == 0 and "campaign: init" in log.stdout.splitlines()
