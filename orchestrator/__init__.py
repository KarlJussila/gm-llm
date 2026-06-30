"""Orchestrator core — the deterministic per-turn loop for the campaign engine.

Drives play over an opencode backend: the runner drafts, the gate always runs, one
bounded correction, then the result is returned. Interfaces (TUI, benchmark) build
on `Game`; nothing here depends on the interface.
"""

from .backend import Backend, BackendError
from .canon import CanonPreloader
from .gate import Gate, GateResult, PlanGateResult, PropagationGateResult, Verdict
from .lifecycle import Lifecycle
from .loop import Game, TurnResult
from .planner import Planner, PlannerError, PrepResult
from .reconciler import Reconciler, ReconcileResult

__all__ = [
    "Backend", "BackendError", "CanonPreloader",
    "Gate", "GateResult", "PlanGateResult", "PropagationGateResult", "Verdict",
    "Game", "TurnResult", "Lifecycle",
    "Planner", "PlannerError", "PrepResult",
    "Reconciler", "ReconcileResult",
]
