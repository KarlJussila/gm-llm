"""Locate the bundled opencode assets — the files opencode itself reads from a
project's `.opencode/` directory (agents, skills, plugin, templates).

These ship with gm-llm and are copied into a project by `gm-llm init`. Two resolutions,
tried in order, so the same code works whether gm-llm is pip-installed or run from a
source checkout / editable install:

  1. **Installed wheel** — assets bundled under `gm_llm/assets/opencode/`.
  2. **Source checkout** — assets still at the repo root (`agent/`, `skills/`, …),
     one level up from this package.
"""

from __future__ import annotations

from pathlib import Path

# The top-level names under the assets root that `init` scaffolds into a project's
# `.opencode/`. Everything opencode reads — nothing Python-only (orchestrator/, tui/).
OPENCODE_ASSET_NAMES = [
    "agent", "skills", "plugin", "templates", "package.json", "package-lock.json",
]


def opencode_assets_dir() -> Path:
    """The directory holding the opencode assets (the `OPENCODE_ASSET_NAMES` live here)."""
    here = Path(__file__).resolve().parent
    bundled = here / "assets" / "opencode"
    if (bundled / "agent").is_dir():
        return bundled                 # installed wheel
    repo = here.parent
    if (repo / "agent").is_dir():
        return repo                    # source checkout / editable install
    raise FileNotFoundError(
        f"gm-llm assets not found (looked in {bundled} and {repo})")
