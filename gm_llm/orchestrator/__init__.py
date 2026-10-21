"""Orchestrator core — the deterministic per-turn loop for the campaign engine.

Drives play over an opencode backend: the player's message goes to the DM and its
reply comes back. Interfaces (TUI, benchmark) build on `Game`; nothing here depends
on the interface.
"""

from .archive import Archive
from .backend import Backend, BackendError
from .canon import CanonPreloader
from .combat import (
    CombatDriver, CombatEvent, CombatRun, CombatState, CombatStep, play_combat,
)
from .gate import Gate, StageGateResult, Verdict
from .lifecycle import Lifecycle
from .logs import Logs
from .loop import Game, TurnResult
from .planner import Planner, PlannerError, PrepResult
from .play import (
    AgentPlayer, KeyboardPlayer, PlayerSource, PlayHooks, PlayResult, play_session,
)
from .reconciler import Reconciler, ReconcileResult
from .setup import Setup, SetupTurn
from .status import CampaignStatus, campaign_status

__all__ = [
    "Archive", "Backend", "BackendError", "CanonPreloader",
    "CampaignStatus", "campaign_status",
    "CombatDriver", "CombatEvent", "CombatRun", "CombatState", "CombatStep", "play_combat",
    "Gate", "StageGateResult", "Verdict",
    "Game", "TurnResult", "Lifecycle", "Logs",
    "AgentPlayer", "KeyboardPlayer", "PlayerSource", "PlayHooks", "PlayResult",
    "play_session",
    "Planner", "PlannerError", "PrepResult",
    "Reconciler", "ReconcileResult",
    "Setup", "SetupTurn",
]
