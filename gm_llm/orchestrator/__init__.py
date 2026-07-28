"""Orchestrator core — the deterministic per-turn loop for the campaign engine.

Drives play over an opencode backend: the runner drafts, the gate always runs, one
bounded correction, then the result is returned. Interfaces (TUI, benchmark) build
on `Game`; nothing here depends on the interface.
"""

from .archive import Archive
from .backend import Backend, BackendError
from .canon import CanonPreloader
from .combat import CombatDriver, CombatEvent, CombatState, CombatStep, play_combat
from .gate import Gate, GateResult, StageGateResult, Verdict
from .lifecycle import Lifecycle
from .logs import Logs
from .loop import Game, TurnResult
from .planner import Planner, PlannerError, PrepResult
from .reconciler import Reconciler, ReconcileResult
from .setup import Setup, SetupTurn
from .status import CampaignStatus, campaign_status

__all__ = [
    "Archive", "Backend", "BackendError", "CanonPreloader",
    "CampaignStatus", "campaign_status",
    "CombatDriver", "CombatEvent", "CombatState", "CombatStep", "play_combat",
    "Gate", "GateResult", "StageGateResult", "Verdict",
    "Game", "TurnResult", "Lifecycle", "Logs",
    "Planner", "PlannerError", "PrepResult",
    "Reconciler", "ReconcileResult",
    "Setup", "SetupTurn",
]
