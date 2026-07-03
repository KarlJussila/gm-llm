"""gm-llm — the command surface.

The primary use is launching the TUI (`gm-llm play`, or a bare `gm-llm`). `init`
scaffolds a new project's `.opencode/`; `doctor` checks the environment. Orchestrator
power-commands (status/prep/reconcile/lint) still live in `dev/cli.py`; this surface is
where future player-facing features grow — talking to the DM to fix canon, rolling a
campaign back to an earlier state, and so on.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _cmd_init(args) -> int:
    from .scaffold import init_project
    dest = init_project(Path(args.dir), force=args.force)
    print(f"initialized opencode assets in {dest}")
    print("next: `gm-llm doctor` to check your environment, then `gm-llm play` here.")
    return 0


def _cmd_doctor(args) -> int:
    from .doctor import run_doctor
    return 0 if run_doctor(Path(args.dir), port=args.port) else 1


def _cmd_play(args) -> int:
    """Launch the Textual TUI against a real opencode backend rooted at `dir`."""
    directory = Path(args.dir).resolve()
    if not (directory / ".opencode" / "agent").is_dir():
        print(f"no .opencode assets in {directory} — run `gm-llm init` here first.",
              file=sys.stderr)
        return 1

    from orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
    from tui.app import PlayApp

    logs = Logs.under(debug=bool(os.environ.get("ORCH_DEBUG")))
    backend = Backend(str(directory), port=args.port, logs=logs).start()
    try:
        gate = Gate(backend, CanonPreloader(str(directory)), logs=logs)
        lifecycle = Lifecycle(backend, gate, str(directory), logs=logs)
        app = PlayApp(lifecycle, cleanup=backend.stop, theme=args.theme)
        app.title = "gm-llm (live)"
        app.run()
    finally:
        backend.stop()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gm-llm", description="An LLM game master for solo D&D campaigns, over opencode.")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("play", help="launch the TUI against a project (the default)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--port", type=int, default=4181)
    p.add_argument("--theme", default="dracula",
                   help="Textual theme (dracula, tokyo-night, gruvbox, nord, …)")
    p.set_defaults(func=_cmd_play)

    p = sub.add_parser("init", help="scaffold opencode assets into a project")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--force", action="store_true", help="overwrite existing assets")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("doctor", help="check the environment (opencode, runtime, port)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--port", type=int, default=4181)
    p.set_defaults(func=_cmd_doctor)

    return ap


def main(argv=None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        # Bare `gm-llm` → play in the current directory (the primary use).
        args = ap.parse_args(["play"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
