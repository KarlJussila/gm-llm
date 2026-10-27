"""
The autonomous player (`--player auto`): the `auto-player` agent plays the PC session after
session with nobody at the keyboard.

It plays on one opencode session for the whole campaign, its id kept in
`.opencode/.orchestrator/auto-player.json`, so it remembers earlier sessions the way a player
would; opencode's compaction keeps the thread going. Its own files live in `player/`, outside the
campaign: `sheet.md`, seeded once from the PC's sheet and kept by the player from then on (it
applies its own level-ups), and `notes.md`, which starts empty and the player keeps as it likes.

A cold start (a first session, or a saved thread the server no longer has) leads with both files
and where the PC stands and what they know; a warm thread is only told a new session has begun.
"""

from __future__ import annotations

import json
from pathlib import Path

from .packet import character_sheet, character_situation
from .play import AgentPlayer
from .prompts import load


def auto_player(backend, directory: str, session: int, story: str | None = None) -> AgentPlayer:
    """The player for session `session`, on its warm thread when the server still has it.
    `story` is the session's play so far, for a cold start into a session underway."""
    root = Path(directory)
    sheet, notes = root / "player" / "sheet.md", root / "player" / "notes.md"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.is_file():
        sheet.write_text(character_sheet(root / "campaign") + "\n", encoding="utf-8")
    if not notes.is_file():  # there to edit: a patch can't always create a file
        notes.write_text("", encoding="utf-8")

    saved = _load(root)
    if saved.get("sid") and backend.session_valid(saved["sid"]):
        sid, story = saved["sid"], None
        same = saved.get("session") == session
        lead = "" if same else load("auto-player-session").format(n=session)
    else:
        sid = backend.create_session("auto-player")
        lead = load("auto-player-lead").format(
            sheet=sheet.read_text(encoding="utf-8").strip(),
            notes=notes.read_text(encoding="utf-8").strip() or "(none yet)",
            situation=character_situation(root / "campaign"))
    _save(root, sid, session)
    return AgentPlayer(backend, sid, lead=lead, story=story, agent="auto-player")


def _state(root: Path) -> Path:
    return root / ".opencode" / ".orchestrator" / "auto-player.json"


def _load(root: Path) -> dict:
    try:
        return json.loads(_state(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(root: Path, sid: str, session: int) -> None:
    path = _state(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sid": sid, "session": session}), encoding="utf-8")
