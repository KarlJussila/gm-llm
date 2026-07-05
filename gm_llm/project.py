"""`gm-llm init` — lay the opencode assets into a target project so opencode can run
there. After init the project holds a `.opencode/` with the agents, skills, and plugin;
the campaign data itself (`campaign/`) is created on the first `gm-llm play` (setup).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .assets import OPENCODE_ASSET_NAMES, opencode_assets_dir

# Package managers to try, in preference order, for the `.opencode` plugin deps.
# package.json carries a per-manager allow-list (allowScripts / trustedDependencies /
# dependenciesMeta / pnpm.onlyBuiltDependencies) so each will run msgpackr-extract's
# native build, which they all block by default now.
_INSTALLERS = ["npm", "bun", "pnpm", "yarn"]


def init_project(directory: Path, *, force: bool = False) -> Path:
    """Copy the opencode assets into `directory/.opencode`. Returns that path.

    Existing assets are left alone unless `force` is set (then overwritten). Only the
    known asset names are copied — never the Python packages or node_modules that sit
    beside them in a source checkout."""
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

    return dest


def install_plugin_deps(opencode_dir: Path) -> tuple[bool, str]:
    """Install the opencode plugin deps in `opencode_dir` (a project's `.opencode`),
    best-effort, with the first available package manager. Returns (ok, message) —
    a failure never raises, so `init` still leaves a usable scaffold behind."""
    opencode_dir = Path(opencode_dir)
    for name in _INSTALLERS:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            if os.name == "nt":
                # npm/bun/pnpm/yarn are .cmd shims on Windows that CreateProcess
                # can't launch directly — route through the shell there.
                proc = subprocess.run(f'"{exe}" install', cwd=opencode_dir,
                                      shell=True, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace")
            else:
                proc = subprocess.run([exe, "install"], cwd=opencode_dir,
                                      capture_output=True, text=True,
                                      encoding="utf-8", errors="replace")
        except OSError as e:
            return False, f"{name} install could not start: {e}"
        if proc.returncode == 0:
            return True, f"plugin deps installed with {name}"
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        return False, f"{name} install failed (exit {proc.returncode}):\n{tail}"
    return False, ("no package manager found (tried npm/bun/pnpm/yarn) — install the plugin "
                   "deps yourself: run `npm install` in the project's .opencode directory")
