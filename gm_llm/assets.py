"""Locate the bundled opencode assets — the files opencode itself reads from a
project's `.opencode/` directory (agents, skills, plugin, templates).

These ship with gm-llm as package data under `gm_llm/assets/opencode/` — the same
path whether gm-llm is pip-installed, editable-installed, or run from a source
checkout — and are copied into a project by `gm-llm init`.
"""

from __future__ import annotations

from pathlib import Path

# The top-level names under the assets root that `init` scaffolds into a project's
# `.opencode/`. Everything opencode reads — nothing Python-only.
OPENCODE_ASSET_NAMES = [
    "agent", "skills", "plugin", "templates", "package.json", "package-lock.json",
]


def opencode_assets_dir() -> Path:
    """The directory holding the opencode assets (the `OPENCODE_ASSET_NAMES` live here)."""
    bundled = Path(__file__).resolve().parent / "assets" / "opencode"
    if not (bundled / "agent").is_dir():
        raise FileNotFoundError(f"gm-llm assets not found at {bundled}")
    return bundled
