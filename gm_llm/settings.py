"""Campaign settings, including the player's shared feedback directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    feedback_dir: Path
    subagents: str = "sequential"

    @property
    def delegation(self) -> str:
        if self.subagents == "parallel":
            return "Independent `task` calls may run concurrently in one message."
        return "Make one `task` call at a time, waiting for it before starting another."


def load_settings(directory: str | Path) -> Settings:
    root = Path(directory).resolve()
    path = root / "gm-llm.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data = data or {}
    subagents = data.get("subagents", "sequential")
    if subagents not in ("sequential", "parallel"):
        raise ValueError(f"{path}: subagents must be sequential or parallel")
    feedback = Path(data.get("feedback-dir", str(Path.home() / ".gm-llm" / "feedback"))).expanduser()
    return Settings((root / feedback).resolve(), subagents)


def init_settings(directory: str | Path) -> None:
    """Write the defaults once. Updates preserve the player's settings."""
    path = Path(directory) / "gm-llm.yaml"
    if not path.exists():
        path.write_text(yaml.safe_dump({
            "feedback-dir": str(Path.home() / ".gm-llm" / "feedback"),
            "subagents": "sequential",
        }, sort_keys=False), encoding="utf-8")
