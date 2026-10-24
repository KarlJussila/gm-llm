"""
Automated setup — a scripted `setup-player` agent answers the dm through campaign setup
(`play --setup-script FILE`). The script's format is in README § Scripted setup: frontmatter
(`character`, `max-turns`), a `## Brief` sent verbatim as the first answer, and whatever else
the agent should follow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .prompts import load
from .registry import split_frontmatter

_BRIEF = re.compile(r"^##\s+Brief\s*\n(.*?)(?=^##\s|\Z)", re.M | re.S | re.I)


class SetupScriptError(ValueError):
    pass


@dataclass
class SetupScript:
    text: str                    # the script as the agent reads it (frontmatter removed)
    brief: str                   # the first answer, sent verbatim ("" leaves it to the agent)
    character: Path | None       # a character file to bring to character creation
    max_turns: int = 20


def load_script(path) -> SetupScript:
    path = Path(path).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SetupScriptError(f"can't read the setup script {path}: {e}") from e
    fm, body = split_frontmatter(raw)
    fm = fm or {}
    character = None
    if fm.get("character"):
        character = Path(str(fm["character"])).expanduser()
        if not character.is_absolute():
            character = path.parent / character
        if not character.is_file():
            raise SetupScriptError(f"the setup script's character file {character} doesn't exist")
    m = _BRIEF.search(body)
    try:
        max_turns = int(fm.get("max-turns", 20))
    except (TypeError, ValueError) as e:
        raise SetupScriptError("max-turns must be a number") from e
    return SetupScript(text=body.strip(), brief=m.group(1).strip() if m else "",
                       character=character, max_turns=max_turns)


class SetupPlayer:
    """The `setup-player` agent on a session of its own. `answer(dm_reply)` returns the
    player's next message: the script's brief, verbatim, to the dm's opening question, then
    the agent's own replies. Its first prompt carries the script, the character file and the
    conversation so far; every later one is the dm's reply alone."""

    def __init__(self, backend, session_id: str, script: SetupScript, agent: str = "setup-player"):
        self.backend = backend
        self.session_id = session_id
        self.script = script
        self.agent = agent
        self.turns = 0
        self._so_far: list[tuple[str, str]] = []
        self._primed = False

    @property
    def exhausted(self) -> bool:
        return self.turns >= self.script.max_turns

    def answer(self, dm_reply: str) -> str:
        self.turns += 1
        if self.turns == 1 and self.script.brief:
            self._so_far += [("dm", dm_reply), ("you", self.script.brief)]
            return self.script.brief
        body = load("player-turn").format(scene=dm_reply)
        if not self._primed:
            self._primed = True
            body = load("setup-player-prime").format(
                script=self.script.text, character=self._character(),
                so_far=self._history()) + "\n\n" + body
        return self.backend.prompt(self.session_id, self.agent, body).strip()

    def _character(self) -> str:
        c = self.script.character
        if c is None:
            return ""
        return load("setup-player-character").format(
            name=c.name, text=c.read_text(encoding="utf-8").strip()) + "\n\n"

    def _history(self) -> str:
        if not self._so_far:
            return "(nothing yet)"
        return "\n\n".join(f"<{who}>\n{text}\n</{who}>" for who, text in self._so_far)
