"""
Init — the orchestrated new-campaign flow.

Setup drives the dm through campaign init as a staged pipeline:
  1. scaffold_campaign()  — pure Python, no LLM
  2. INTAKE_WORLD         — dm does intake + world build (interactive with player)
  3. CHAR                 — dm does character creation (interactive with player)
  4. ARC_MAJOR, ARC_MINOR, STATE — single-turn dispatches, no player
  5. GATE                 — init-gate checker in a fresh session
  6. COMMIT               — git commit in code

  s = Setup(backend, gate, directory)
  s.start()                 # scaffold, open first brief, return dm's first message
  s.turn(player_input)      # relay player turn; advance stage on completion signals
  s.finalize()              # once done: plan session 1 (code-gated + committed)

Stage markers in .opencode/.orchestrator/setup-{stage}.done track progress and enable resume.
The interactive stages (INTAKE_WORLD, CHAR) advance when the dm calls the `task_complete` tool —
its own explicit "I'm done" signal — not by inferring completion from a canon file appearing
mid-conversation (which fired the transition before the dm had finished talking to the player).
The non-interactive stages stop when their dispatch returns, like the reconciler. Overall
completion is still read from git/disk — never by parsing the dm's prose.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .phase import apply_one_correction, commit_campaign
from .planner import Planner
from .prompts import load
from .scaffold import scaffold_campaign

_STAGE_BRIEFS = {
    "INTAKE_WORLD": "setup-intake-world-brief",
    "CHAR":         "setup-char-brief",
    "ARC_MAJOR":    "setup-arc-major-brief",
    "ARC_MINOR":    "setup-arc-minor-brief",
    "STATE":        "setup-state-brief",
}

# Stage → the key announced to a watcher (the TUI's ticker) — the same on_stage
# protocol the Reconciler speaks, so one UI renderer covers the whole lifecycle.
_STAGE_KEYS = {
    "INTAKE_WORLD": "intake",
    "CHAR":         "char",
    "ARC_MAJOR":    "arc-major",
    "ARC_MINOR":    "arc-minor",
    "STATE":        "state",
    "GATE":         "gate",
    "COMMIT":       "commit",
}


@dataclass
class SetupTurn:
    reply: str   # the dm's message to the player this exchange
    done: bool   # True once `campaign: init` is committed — time to finalize


class Setup:
    """Drives the dm through campaign init as a staged, orchestrator-controlled pipeline."""

    def __init__(self, backend, gate, directory: str, dm_agent: str = "dm",
                 on_prep=None, on_stage=None, logs=None):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.dm_agent = dm_agent
        self.on_prep = on_prep
        self.on_stage = on_stage  # called with a stage key as each stage starts (TUI ticker)
        self.logs = logs
        self.root = Path(directory)
        self._stage: str | None = None
        self.dm_sid: str | None = None

    def _announce(self, stage: str) -> None:
        """Tell a watcher (e.g. the TUI ticker) which stage is starting — the same
        protocol as Reconciler.on_stage."""
        if self.on_stage:
            try:
                self.on_stage(_STAGE_KEYS.get(stage, stage.lower()))
            except Exception:
                pass

    def start(self) -> SetupTurn:
        if self._init_committed():
            return SetupTurn("This directory already has a campaign — planning the first session.", True)

        scaffold_campaign(self.root)
        self.dm_sid = self.backend.create_session("dm setup")
        self._stage = self._resume_stage()

        # Non-interactive resume: run the pipeline immediately, no player turns needed
        if self._stage not in ("INTAKE_WORLD", "CHAR"):
            self._run_pipeline()
            return SetupTurn("Campaign init complete.", True)

        # whole=True: the dm's player-facing setup message can span several text parts (it
        # works as it talks — e.g. the world overview followed by a short closer), and
        # _last_text would surface only the final fragment, dropping the overview. Joining
        # all text parts surfaces the whole message; reasoning/tool parts are excluded, so
        # the behind-the-screen thinking never leaks in.
        self._announce(self._stage)
        reply = self.backend.prompt(self.dm_sid, self.dm_agent,
                                    load(_STAGE_BRIEFS[self._stage]), whole=True)
        return SetupTurn(reply, False)

    def turn(self, player_input: str) -> SetupTurn:
        reply = self.backend.prompt_full(self.dm_sid, self.dm_agent, player_input, whole=True)
        text, done = reply.text, "task_complete" in reply.tools

        if self._stage == "INTAKE_WORLD" and done:
            self._mark_done("INTAKE_WORLD")
            self._stage = "CHAR"
            self._announce("CHAR")
            # Open character creation and APPEND it to the world wrap-up, so the player
            # sees both this turn — never overwrite the dm's own closing beat.
            char_open = self.backend.prompt(self.dm_sid, self.dm_agent,
                                            load("setup-char-brief"), whole=True)
            return SetupTurn(f"{text}\n\n{char_open}", False)
        if self._stage == "CHAR" and done:
            self._mark_done("CHAR")
            self._run_pipeline()
            return SetupTurn(text, True)

        return SetupTurn(text, self._init_committed())

    def finalize(self) -> int:
        """Once init is committed, plan session 1 via Planner, reusing the warm dm thread."""
        Planner(self.backend, self.gate, dm_agent=self.dm_agent, dm_sid=self.dm_sid,
                on_prep=self.on_prep, logs=self.logs).prep_session(1, commit=True)
        return 1

    # --- non-interactive pipeline ---

    def _run_pipeline(self) -> None:
        """Arc design, state init, gate, and commit — no player turns."""
        for stage, brief_key in [
            ("ARC_MAJOR", "setup-arc-major-brief"),
            ("ARC_MINOR", "setup-arc-minor-brief"),
            ("STATE",     "setup-state-brief"),
        ]:
            if not self._setup_done(stage):
                self._announce(stage)
                self.backend.prompt(self.dm_sid, self.dm_agent, load(brief_key))
                self._mark_done(stage)

        if not self._setup_done("GATE"):
            self._announce("GATE")
            result = self.gate.check_init()
            apply_one_correction(self.backend, self.dm_sid, self.dm_agent, result)
            self._mark_done("GATE")

        self._announce("COMMIT")
        commit_campaign(self.root, "campaign: init")
        self._mark_done("COMMIT")

    # --- stage tracking ---

    def _resume_stage(self) -> str:
        """First stage without a completion marker. Markers are the single source of
        truth (matches the reconciler) — the interactive stages mark done when the dm
        signals `task_complete`, so there's no canon-file guessing here anymore."""
        for stage in ("INTAKE_WORLD", "CHAR", "ARC_MAJOR", "ARC_MINOR", "STATE", "GATE"):
            if not self._setup_done(stage):
                return stage
        return "COMMIT"

    def _setup_done(self, stage: str) -> bool:
        return self._marker(stage).is_file()

    def _mark_done(self, stage: str) -> None:
        self._marker(stage).write_text(datetime.now(timezone.utc).isoformat() + "\n")

    def _marker(self, stage: str) -> Path:
        d = self.root / ".opencode" / ".orchestrator"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"setup-{stage}.done"

    # --- completion ---

    def _init_committed(self) -> bool:
        """Done iff `campaign: init` is in the campaign repo's history (or session 1
        is already planned). A robust file/git signal — we never prose-parse the dm."""
        if (self.root / "campaign" / "sessions" / "session-1-plan.md").is_file():
            return True
        try:
            log = subprocess.run(["git", "log", "--pretty=%s"], cwd=self.root,
                                 capture_output=True, text=True)
        except OSError:
            return False
        return log.returncode == 0 and "campaign: init" in log.stdout.splitlines()
