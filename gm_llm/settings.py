"""The project's `gm-llm.yaml`: where the player's feedback lives, and how subagents run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULTS = {"feedback-dir": "~/.gm-llm/feedback", "subagents": "sequential"}


@dataclass(frozen=True)
class Settings:
    feedback_dir: Path
    subagents: str   # sequential | parallel; the brief sentence is prompts/subagents-<value>.md


def load_settings(directory: str | Path) -> Settings:
    root = Path(directory).resolve()
    path = root / "gm-llm.yaml"
    user = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    data = {**_DEFAULTS, **(user or {})}
    if data["subagents"] not in ("sequential", "parallel"):
        raise ValueError(f"{path}: subagents must be sequential or parallel")
    return Settings((root / Path(data["feedback-dir"]).expanduser()).resolve(), data["subagents"])


def init_settings(directory: str | Path) -> None:
    """Write the defaults once; the agents read `feedback-dir` from this file."""
    path = Path(directory) / "gm-llm.yaml"
    if not path.exists():
        path.write_text(yaml.safe_dump(_DEFAULTS, sort_keys=False), encoding="utf-8")
