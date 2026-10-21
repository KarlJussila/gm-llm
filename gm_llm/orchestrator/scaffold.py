"""
Campaign scaffolding — creates the empty campaign/ directory tree.

First step of init, run in Python before any LLM session is created. No LLM
involved. Idempotent: skips silently if campaign/ already exists.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from gm_llm.assets import opencode_assets_dir

from .registry import write_index


def _skill_templates() -> Path:
    """The canon-conventions templates in the bundled assets — resolved at call time
    so importing this module never touches the filesystem."""
    return opencode_assets_dir() / "skills" / "canon-conventions" / "templates"


_SUBDIRS = [
    "world/npcs", "world/factions", "world/locations",
    "world/items", "world/regions", "world/concepts", "world/bestiary",
    "arcs", "state", "characters", "sessions",
    "documents",
]

_STATE_FILES = [
    "state-current", "state-calendar", "state-threads", "state-clocks",
]


def scaffold_campaign(directory: Path) -> None:
    """Create the campaign/ tree. Skips silently if campaign/ already exists."""
    root = Path(directory)
    campaign = root / "campaign"
    if campaign.exists():
        return

    _ensure_git(root)
    _ensure_gitignore(root)

    for subdir in _SUBDIRS:
        (campaign / subdir).mkdir(parents=True, exist_ok=True)

    _write_index(campaign)
    _write_state_files(campaign)


def _ensure_git(root: Path) -> None:
    if not (root / ".git").exists():
        subprocess.run(["git", "init"], cwd=root, capture_output=True)


def _ensure_gitignore(root: Path) -> None:
    gitignore = root / ".gitignore"
    line = ".opencode/"
    if not gitignore.exists():
        gitignore.write_text(line + "\n", encoding="utf-8")
    elif line not in gitignore.read_text(encoding="utf-8").splitlines():
        with gitignore.open("a", encoding="utf-8") as f:
            f.write("\n" + line + "\n")


def _write_index(campaign: Path) -> None:
    """An empty campaign's generated registry."""
    write_index(campaign)


def _write_state_files(campaign: Path) -> None:
    state_dir = campaign / "state"
    templates = _skill_templates()
    for name in _STATE_FILES:
        template = (templates / f"{name}.template.md").read_text(encoding="utf-8")
        content = template.replace("S<n>", "S0")
        out_name = name.removeprefix("state-") + ".md"
        (state_dir / out_name).write_text(content, encoding="utf-8")
