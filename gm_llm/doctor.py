"""`gm-llm doctor` — check that the environment can actually run gm-llm, and print
exactly what's missing. This is the single biggest setup lever: opencode + a JS runtime
+ a configured provider are the real prerequisites on every OS, and they're where a
newcomer gets stuck.
"""

from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    warn: bool = False   # a failed warn-check reports ✗ but doesn't fail `doctor`


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) != 0


def collect(directory: Path, port: int = 4181) -> list[Check]:
    opencode = shutil.which("opencode")
    runtime = shutil.which("bun") or shutil.which("node")
    npm = shutil.which("npm") or shutil.which("bun")
    initialized = (Path(directory) / ".opencode" / "agent").is_dir()
    return [
        Check("opencode on PATH", bool(opencode),
              opencode or "not found — install from https://opencode.ai"),
        Check("JS runtime (bun/node)", bool(runtime),
              runtime or "not found — opencode needs bun or node"),
        Check("plugin installer (bun/npm)", bool(npm),
              npm or "not found — needed to install the .opencode plugin deps", warn=True),
        Check(f"port {port} free", _port_free(port),
              "free" if _port_free(port) else "in use — a server may already be running",
              warn=True),
        Check(f"project initialized ({directory})", initialized,
              "yes" if initialized else "run `gm-llm init` here first"),
    ]


def run_doctor(directory: Path, port: int = 4181) -> bool:
    """Print the checklist; return True if nothing blocking failed (warnings don't block)."""
    checks = collect(directory, port)
    for c in checks:
        print(f"  {'✓' if c.ok else '✗'} {c.name}: {c.detail}")
    print("  · reminder: opencode needs a provider configured for the model your agents "
          "use (e.g. `opencode auth`); doctor can't verify that for you.")
    return all(c.ok for c in checks if not c.warn)
