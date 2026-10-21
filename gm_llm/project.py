"""`gm-llm init` — lay the opencode assets into a target project so opencode can run
there. After init the project holds a `.opencode/` with the agents, skills, and plugin;
the campaign data itself (`campaign/`) is created on the first `gm-llm play` (setup).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .assets import OPENCODE_ASSET_NAMES, opencode_assets_dir

# What older gm-llm versions put in `.opencode/` and this one no longer uses: the plugins
# needed an npm install under opencode 1.x, and need nothing under 2.x.
_RETIRED = ["package.json", "package-lock.json", "node_modules"]


def init_project(directory: Path, *, force: bool = False) -> Path:
    """Copy the opencode assets into `directory/.opencode`. Returns that path.

    Existing assets are left alone unless `force` is set (then overwritten, and what older
    versions left behind is removed). Only the known asset names are copied."""
    directory = Path(directory).resolve()
    src = opencode_assets_dir()
    dest = directory / ".opencode"
    dest.mkdir(parents=True, exist_ok=True)

    for name in OPENCODE_ASSET_NAMES:
        s = src / name
        if not s.exists():
            continue
        d = dest / name
        if d.exists():
            if not force:
                continue
            shutil.rmtree(d) if d.is_dir() else d.unlink()
        shutil.copytree(s, d) if s.is_dir() else shutil.copy2(s, d)

    if force:
        for name in _RETIRED:
            d = dest / name
            if d.exists():
                shutil.rmtree(d) if d.is_dir() else d.unlink()
    return dest
