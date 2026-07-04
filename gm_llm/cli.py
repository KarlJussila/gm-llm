"""gm-llm — the command surface.

The primary use is launching the TUI (`gm-llm play`, or a bare `gm-llm`). `init`
scaffolds a new project's `.opencode/`; `doctor` checks the environment. Orchestrator
power-commands (status/prep/reconcile/lint) still live in `dev/cli.py`; this surface is
where future player-facing features grow — talking to the DM to fix canon, rolling a
campaign back to an earlier state, and so on.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _install_deps(dest: Path, skip: bool, *, verb: str) -> None:
    """Shared by init/update: run (or skip) the plugin-deps install and report."""
    if skip:
        print("skipped plugin-deps install (--no-install).")
        return
    from .project import install_plugin_deps
    print(f"{verb} plugin deps (dice / report / task-complete) …")
    ok, msg = install_plugin_deps(dest)
    print(f"  {'✓' if ok else '✗'} {msg}")


def _cmd_init(args) -> int:
    from .project import init_project
    dest = init_project(Path(args.dir), force=args.force)
    print(f"initialized opencode assets in {dest}")
    _install_deps(dest, args.no_install, verb="installing")
    print("next: `gm-llm doctor` to check your environment, then `gm-llm play`.")
    return 0


def _cmd_update(args) -> int:
    """Refresh an existing project's framework assets to this gm-llm version."""
    from .project import init_project
    directory = Path(args.dir).resolve()
    if not (directory / ".opencode" / "agent").is_dir():
        print(f"{directory} isn't a gm-llm project (no .opencode/agent) — "
              f"use `gm-llm init` to create one.", file=sys.stderr)
        return 1
    dest = init_project(directory, force=True)   # overwrite the framework assets
    print(f"updated framework assets in {dest} (to gm-llm {__version__})")
    _install_deps(dest, args.no_install, verb="refreshing")
    print("your campaign/ data, .orchestrator markers, and node_modules were left untouched.")
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

    from .orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
    from .orchestrator.logs import debug_enabled
    from .tui.app import PlayApp

    logs = Logs.under(project=directory, debug=debug_enabled())
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
    ap.add_argument("--version", action="version", version=f"gm-llm {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("play", help="launch the TUI against a project (the default)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--port", type=int, default=4181)
    p.add_argument("--theme", default="dracula",
                   help="Textual theme (dracula, tokyo-night, gruvbox, nord, …)")
    p.set_defaults(func=_cmd_play)

    p = sub.add_parser("init", help="scaffold opencode assets into a project + install plugin deps")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--force", action="store_true", help="overwrite existing assets")
    p.add_argument("--no-install", action="store_true", help="skip installing the .opencode plugin deps")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("update", help="refresh an existing project's framework assets to this version")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--no-install", action="store_true", help="skip refreshing the .opencode plugin deps")
    p.set_defaults(func=_cmd_update)

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
