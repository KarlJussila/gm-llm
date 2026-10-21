"""
Shared primitives for the orchestrated between-sessions phases (PRE planning,
POST reconcile).

Both phases share one deterministic spine: the author writes, the orchestrator ALWAYS
gates in code, applies exactly ONE bounded correction, then commits deterministically. The two invariants that make that safe —
*one* correction (never a re-gate loop) and *code-owned* git — live here, in one
place, so PRE and POST can't drift apart.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import lint
from .prompts import load
from .registry import write_index
from .reveals import sync_reveals


def correct_once(backend, session_id: str, agent: str, gate_result, root: str | Path) -> str | None:
    """The bounded-correction primitive. If the gate found violations, hand the agent its
    correction brief EXACTLY ONCE — no re-gate, no loop. Returns None when no correction was
    needed, else the diff the correction made under `campaign/` ('' if it changed nothing) —
    the before/after every gate archives. The caller re-reads whatever artifact it owns."""
    if not gate_result.violations:
        return None
    before = _campaign_tree(root)
    backend.prompt(session_id, agent, gate_result.correction_brief())
    after = _campaign_tree(root)
    if not (before and after) or before == after:
        return ""
    return _git(root, "diff", "--src-prefix=a/campaign/", "--dst-prefix=b/campaign/",
                before, after) or ""


def _campaign_tree(root: str | Path) -> str | None:
    """A git tree id for `campaign/` as it stands on disk, or None outside a repo. Stages
    `campaign/` to get it, which the commit at the end of every phase does anyway."""
    if _git(root, "add", "-A", "--", "campaign") is None:
        return None
    tree = _git(root, "write-tree", "--prefix=campaign/")
    return tree.strip() if tree else None


def _git(root: str | Path, *args: str) -> str | None:
    """Run git in `root`; its stdout, or None on failure. Best-effort, never raises."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def refresh_campaign(root: str | Path) -> None:
    """Bring the derived files up to date: flip the reveals the knowledge ledger records,
    then regenerate INDEX.md. Run after any authoring dispatch and before a commit."""
    campaign = Path(root) / "campaign"
    if campaign.is_dir():
        sync_reveals(campaign)
        write_index(campaign)


def apply_lint_correction(backend, session_id: str, agent: str, root: str | Path) -> list:
    """Refresh, run the canon lint, and if it found anything send the issues back to the
    authoring agent exactly ONCE (no re-lint loop), then refresh again. Returns the issues
    found before the correction (empty when the campaign was clean)."""
    refresh_campaign(root)
    issues = lint.lint_campaign(root)
    if issues:
        backend.prompt(session_id, agent, load("correct-lint") + "\n\n" + lint.brief(issues))
        refresh_campaign(root)
    return issues


def commit_campaign(root: str | Path, message: str) -> bool:
    """Commit the campaign repo deterministically (the orchestrator owns git, not the
    model). Stages only `campaign/`; no-ops if the pass produced no change.
    Best-effort — a git failure never breaks the phase."""
    root = Path(root)
    refresh_campaign(root)
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
