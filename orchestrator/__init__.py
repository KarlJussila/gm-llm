"""Orchestrator core — the deterministic per-turn loop for the campaign engine.

Drives play over an opencode backend: the runner drafts, the gate always runs, one
bounded correction, then the result is returned. Interfaces (TUI, benchmark) build
on `Game`; nothing here depends on the interface.
"""

from .backend import Backend, BackendError
from .canon import CanonPreloader
from .gate import Gate, GateResult, Verdict
from .loop import Game, TurnResult

__all__ = [
    "Backend", "BackendError", "CanonPreloader",
    "Gate", "GateResult", "Verdict", "Game", "TurnResult",
]
