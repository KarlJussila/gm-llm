"""
Init — the orchestrated new-campaign flow.

Setup drives the dm through campaign init as a staged pipeline:
  1. scaffold_campaign()  — pure Python, no LLM
  2. INTAKE               — dm gathers the brief and pitches the world (interactive with player)
  3. WORLD                — one dispatch: the world built from the pitch
  4. CHAR                 — dm does character creation (interactive with player)
  5. ARCS_STATE           — one dispatch: arcs, initial state, then the player's primer;
                            disk-based coverage check
  6. LINT, GATE           — canon lint, then judgment in a fresh session
  7. COMMIT               — git commit in code

  s = Setup(backend, gate, directory)
  s.start()                 # scaffold, open first brief, return dm's first message
  s.turn(player_input)      # relay player turn; advance stage on completion signals
  s.finalize()              # once done: plan session 1 (code-gated + committed)

Stage markers in .opencode/.orchestrator/setup-{stage}.done track progress and enable resume.
The interactive stages (INTAKE, CHAR) advance when the dm calls the `task_complete` tool —
its own explicit "I'm done" signal — not by inferring completion from a canon file appearing
mid-conversation (which fired the transition before the dm had finished talking to the player).
The non-interactive stages stop when their dispatch returns, like the reconciler. Overall
completion is still read from git/disk — never by parsing the dm's prose.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .archive import verdict_fields
from . import paths
from .canon import dm_guidance
from .lint import setup_missing
from .loop import join_narration
from .phase import apply_lint_correction, commit_campaign, correct_once, refresh_campaign
from .planner import Planner
from .prompts import load
from .scaffold import scaffold_campaign

_STAGE_BRIEFS = {
    "INTAKE":       "setup-intake-brief",
    "CHAR":         "setup-char-brief",
}

# Stage → the key announced to a watcher (the TUI's ticker) — the same on_stage
# protocol the Reconciler speaks, so one UI renderer covers the whole lifecycle.
_STAGE_KEYS = {
    "INTAKE":       "intake",
    "WORLD":        "world",
    "CHAR":         "char",
    "ARCS_STATE":   "arcs-state",
    "LINT":         "lint",
    "GATE":         "gate",
    "COMMIT":       "commit",
}


# Code, not the dm, points the player to their primer once setup has written it.
_PRIMER_READY = ("Your primer is ready: `campaign/documents/primer.md`, the world as your "
                 "character knows it before play begins.")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


@dataclass
class SetupTurn:
    reply: str   # the dm's message to the player this exchange
    done: bool   # True once `campaign: init` is committed — time to finalize


class Setup:
    """Drives the dm through campaign init as a staged, orchestrator-controlled pipeline."""

    def __init__(self, backend, gate, directory: str, dm_agent: str = "dm",
                 on_prep=None, on_stage=None, logs=None, character_file: Path | None = None):
        self.backend = backend
        self.gate = gate
        self.directory = directory
        self.dm_agent = dm_agent
        self.on_prep = on_prep
        self.on_stage = on_stage  # called with a stage key as each stage starts (TUI ticker)
        self.logs = logs
        self.root = Path(directory)
        # A character file the player brings (a setup script's `character:`), placed among the
        # campaign's documents as character creation opens — as a player would drop it in.
        self.character_file = character_file
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
        self.backend.preface(self.dm_sid, dm_guidance(self.root))
        self._stage = self._resume_stage()

        # A resume between the interactive stages builds the world, then opens character creation
        if self._stage == "WORLD":
            self._build_world()
            self._stage = "CHAR"

        # Non-interactive resume: run the pipeline immediately, no player turns needed
        if self._stage not in ("INTAKE", "CHAR"):
            self._run_pipeline()
            return SetupTurn(self._finished("Campaign init complete."), True)

        self._announce(self._stage)
        if self._stage == "CHAR":
            self._bring_character()
        reply = self.backend.prompt(self.dm_sid, self.dm_agent,
                                    load(_STAGE_BRIEFS[self._stage]))
        refresh_campaign(self.root)
        return SetupTurn(reply, False)

    def turn(self, player_input: str) -> SetupTurn:
        reply = self.backend.prompt_full(self.dm_sid, self.dm_agent, player_input)
        refresh_campaign(self.root)
        text = reply.text
        done = "task_complete" in reply.tools

        if self._stage == "INTAKE" and done:
            self._mark_done("INTAKE")
            self._build_world()
            self._stage = "CHAR"
            self._announce("CHAR")
            self._bring_character()
            char_open = self.backend.prompt(self.dm_sid, self.dm_agent,
                                            load("setup-char-brief"))
            refresh_campaign(self.root)
            return SetupTurn(join_narration(text, char_open), False)
        if self._stage == "CHAR" and done:
            self._mark_done("CHAR")
            self._run_pipeline()
            return SetupTurn(self._finished(text), True)

        return SetupTurn(text, self._init_committed())

    def finalize(self) -> int:
        """Once init is committed, plan session 1 via Planner, reusing the warm dm thread."""
        Planner(self.backend, self.gate, dm_agent=self.dm_agent, dm_sid=self.dm_sid,
                on_prep=self.on_prep, logs=self.logs).prep_session(1, commit=True)
        return 1

    def _bring_character(self) -> None:
        if self.character_file is None:
            return
        dest = self.root / "campaign" / "documents" / self.character_file.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.character_file, dest)

    # --- non-interactive stages ---

    def _build_world(self) -> None:
        """The world from the approved pitch, top down."""
        self._announce("WORLD")
        self.backend.prompt(self.dm_sid, self.dm_agent, load("setup-world-brief"))
        if self.logs and self.logs.archive:
            self.logs.archive.emit("stage", stage="world")
        refresh_campaign(self.root)
        self._mark_done("WORLD")

    def _run_pipeline(self) -> None:
        """Arcs and state, lint, gate, and commit — no player turns."""
        # One dispatch over what the disk still lacks (everything, unless a resume finds
        # some of it done), then one nudge naming anything still missing.
        if not self._setup_done("ARCS_STATE"):
            self._announce("ARCS_STATE")
            self.backend.prompt(self.dm_sid, self.dm_agent, load("setup-arcs-state-brief").format(
                missing=_bullets(setup_missing(self.root))))
            missing = setup_missing(self.root)
            if missing:
                self.backend.prompt(self.dm_sid, self.dm_agent, load("setup-missing").format(
                    missing=_bullets(missing)))
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="arcs-state", missed=missing,
                                       still_missed=setup_missing(self.root))
            self._mark_done("ARCS_STATE")

        if not self._setup_done("LINT"):
            self._announce("LINT")
            issues = apply_lint_correction(self.backend, self.dm_sid, self.dm_agent, self.root)
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="lint", incomplete=len(issues),
                                       corrected=bool(issues))
            self._mark_done("LINT")

        if not self._setup_done("GATE"):
            self._announce("GATE")
            result = self.gate.check_init()
            diff = correct_once(self.backend, self.dm_sid, self.dm_agent, result, self.root)
            if self.logs and self.logs.archive:
                self.logs.archive.emit("stage", stage="init",
                                       verdict=verdict_fields(result.narrative),
                                       corrected=diff is not None, diff=diff or "")
            self._mark_done("GATE")

        self._announce("COMMIT")
        commit_campaign(self.root, "campaign: init")
        self._mark_done("COMMIT")

    def _finished(self, text: str) -> str:
        """Setup's last word to the player, with the pointer to their primer."""
        if (self.root / "campaign" / "documents" / "primer.md").is_file():
            return join_narration(text, _PRIMER_READY)
        return text

    # --- stage tracking ---

    def _resume_stage(self) -> str:
        """First stage without a completion marker."""
        for stage in ("INTAKE", "WORLD", "CHAR", "ARCS_STATE", "LINT", "GATE"):
            if not self._setup_done(stage):
                return stage
        return "COMMIT"

    def _setup_done(self, stage: str) -> bool:
        return self._marker(stage).is_file()

    def _mark_done(self, stage: str) -> None:
        self._marker(stage).write_text(datetime.now(timezone.utc).isoformat() + "\n",
                                       encoding="utf-8")

    def _marker(self, stage: str) -> Path:
        d = self.root / ".opencode" / ".orchestrator"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"setup-{stage}.done"

    # --- completion ---

    def _init_committed(self) -> bool:
        """Done iff `campaign: init` is in the campaign repo's history (or session 1
        is already planned). A robust file/git signal — we never prose-parse the dm."""
        if paths.plan(self.root / "campaign", 1).is_file():
            return True
        try:
            log = subprocess.run(["git", "log", "--pretty=%s"], cwd=self.root,
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        except OSError:
            return False
        return log.returncode == 0 and "campaign: init" in log.stdout.splitlines()
