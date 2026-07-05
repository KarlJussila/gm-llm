"""
Where the campaign stands — read from disk only, no server, no model.

One source of truth for the "status" view: `cli.py status` renders it to the
terminal and the TUI's status modal renders it in-app, both over the same
`CampaignStatus` snapshot so they can't drift.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .canon import latest_session
from .completeness import lint_dir

# The per-session artifacts the pipeline produces, in pipeline order.
# Paths are relative to campaign/sessions/.
_ARTIFACTS = (
    ("plan", "session-{n}-plan.md"),
    ("transcript", "session-{n}-transcript.md"),
    ("notes", "session-{n}-notes.md"),
    ("digest", "session-{n}.md"),
    ("assessment", "../assessment/session-{n}-assessment.md"),
)


@dataclass
class CampaignStatus:
    root: Path
    phase: str                                  # "setup" | "play"
    session: int | None                         # latest session, None during setup
    artifacts: list[tuple[str, bool]] = field(default_factory=list)  # (name, present)
    reconcile_stages: list[str] = field(default_factory=list)        # completed reconcile-{n}-* stages
    entities_total: int = 0
    entities_complete: int = 0
    incomplete: list[str] = field(default_factory=list)  # relative paths of flagged entity files
    git_state: str | None = None                # "clean" | "dirty" | None (git unavailable)
    last_commit: str | None = None


def campaign_status(directory: str | Path) -> CampaignStatus:
    """Snapshot the campaign's standing from disk. Safe to call in any phase —
    a brand-new directory just reports setup with everything empty."""
    root = Path(directory)
    sessions = root / "campaign" / "sessions"
    n = latest_session(sessions)
    st = CampaignStatus(root=root, phase="setup" if n is None else "play", session=n)

    if n is not None:
        st.artifacts = [(name, (sessions / rel.format(n=n)).resolve().is_file())
                        for name, rel in _ARTIFACTS]
        markers_dir = root / ".opencode" / ".orchestrator"
        if markers_dir.is_dir():
            prefix, suffix = f"reconcile-{n}-", ".done"
            st.reconcile_stages = [
                name[len(prefix):-len(suffix)]
                for name in sorted(p.name for p in markers_dir.glob(f"{prefix}*{suffix}"))]

    reports = lint_dir(root)
    st.entities_total = len(reports)
    st.entities_complete = sum(1 for r in reports if r.ok)
    st.incomplete = [str(r.path.relative_to(root) if r.path.is_absolute() else r.path)
                     for r in reports if not r.ok]

    try:
        git = subprocess.run(["git", "status", "--porcelain", "--", "campaign"],
                             cwd=root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        if git.returncode == 0:
            st.git_state = "dirty" if git.stdout.strip() else "clean"
            last = subprocess.run(["git", "log", "-1", "--pretty=%s"],
                                  cwd=root, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace").stdout.strip()
            st.last_commit = last or None
    except OSError:
        pass
    return st
