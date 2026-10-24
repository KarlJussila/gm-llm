"""
Where a session's files live: one folder per session, `campaign/sessions/<n>/`.

    plan.md        the prepared session plan (its existence is what makes <n> a session)
    prologue.md    session 1 only: read to the player verbatim as the session opens
    transcript.md  the orchestrator-written play record
    notes.md       the DM's closing handoff notes
    digest.md      the post-session extraction every later step reads

Every module that touches a session file goes through here, so the layout has one home.
"""

from __future__ import annotations

from pathlib import Path


def session_dir(campaign: Path | str, n: int) -> Path:
    return Path(campaign) / "sessions" / str(n)


def plan(campaign: Path | str, n: int) -> Path:
    return session_dir(campaign, n) / "plan.md"


def prologue(campaign: Path | str, n: int) -> Path:
    return session_dir(campaign, n) / "prologue.md"


def transcript(campaign: Path | str, n: int) -> Path:
    return session_dir(campaign, n) / "transcript.md"


def notes(campaign: Path | str, n: int) -> Path:
    return session_dir(campaign, n) / "notes.md"


def digest(campaign: Path | str, n: int) -> Path:
    return session_dir(campaign, n) / "digest.md"


def rel(n: int, name: str) -> str:
    """A session file's path relative to campaign/, as prompts and preload headers name it."""
    return f"sessions/{n}/{name}.md"


def latest_session(campaign: Path | str) -> int | None:
    """The current session: the highest `sessions/<n>/` holding a plan (None if none)."""
    best = 0
    try:
        for d in (Path(campaign) / "sessions").iterdir():
            if d.is_dir() and d.name.isdigit() and (d / "plan.md").is_file():
                best = max(best, int(d.name))
    except OSError:
        return None
    return best or None
