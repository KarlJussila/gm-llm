"""The project's `gm-llm.yaml`: where the player's feedback lives, and how subagents run.

The agents can't reach outside the project, so they never see `feedback-dir` itself: they read
and curate the project's `feedback/`, which the orchestrator fills from the player's store and
copies curation back from."""

from __future__ import annotations

import shutil
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
    """Write the defaults once."""
    path = Path(directory) / "gm-llm.yaml"
    if not path.exists():
        path.write_text(yaml.safe_dump(_DEFAULTS, sort_keys=False), encoding="utf-8")


def project_feedback(directory: str | Path) -> Path:
    """The project's copy of the player's feedback — what the agents read and curate."""
    return Path(directory).resolve() / "feedback"


def pull_feedback(directory: str | Path) -> None:
    """Copy the player's feedback store into the project's `feedback/`. A no-op when the store
    is that directory (a benchmark run's private copy)."""
    store, here = load_settings(directory).feedback_dir, project_feedback(directory)
    if store == here or not store.is_dir():
        return
    here.mkdir(exist_ok=True)
    for f in store.glob("*.md"):
        shutil.copy2(f, here / f.name)


def feedback_snapshot(directory: str | Path) -> dict[str, bytes]:
    here = project_feedback(directory)
    return {f.name: f.read_bytes() for f in here.glob("*.md")} if here.is_dir() else {}


def push_feedback(directory: str | Path, before: dict[str, bytes]) -> None:
    """Copy back to the player's store the files curation changed since `before` — only
    those, so another campaign's curation since the pull survives."""
    store, here = load_settings(directory).feedback_dir, project_feedback(directory)
    if store == here:
        return
    for name, data in feedback_snapshot(directory).items():
        if before.get(name) != data:
            store.mkdir(parents=True, exist_ok=True)
            shutil.copy2(here / name, store / name)
