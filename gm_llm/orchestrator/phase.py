"""
Shared primitives for the orchestrated between-sessions phases (PRE planning,
POST reconcile).

Both phases have the same deterministic spine as the per-turn loop, one stage out:
the `dm` authors, the orchestrator ALWAYS gates in code, applies exactly ONE bounded
correction, then commits deterministically. The two invariants that make that safe —
*one* correction (never a re-gate loop) and *code-owned* git — live here, in one
place, so PRE and POST can't drift apart.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def apply_one_correction(backend, session_id: str, agent: str, gate_result) -> bool:
    """The bounded-correction primitive. If the gate found violations, hand the
    agent its correction brief EXACTLY ONCE — no re-gate, no loop — and report that
    a correction was made. `gate_result` is any *GateResult with `.violations` and
    `.correction_brief()`. The caller re-reads whatever artifact it owns afterward."""
    if not gate_result.violations:
        return False
    backend.prompt(session_id, agent, gate_result.correction_brief())
    return True


def commit_campaign(root: str | Path, message: str) -> bool:
    """Commit the campaign repo deterministically (the orchestrator owns git, not the
    model). Stages only `campaign/`; no-ops if the pass produced no change.
    Best-effort — a git failure never breaks the phase."""
    root = Path(root)
    try:
        staged = subprocess.run(["git", "add", "--", "campaign"],
                                cwd=root, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if staged.returncode != 0:
            return False
        dirty = subprocess.run(["git", "diff", "--cached", "--quiet"],
                               cwd=root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if dirty.returncode == 0:  # nothing staged -> nothing to commit
            return False
        done = subprocess.run(["git", "commit", "-m", message],
                              cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return done.returncode == 0
    except OSError:
        return False
