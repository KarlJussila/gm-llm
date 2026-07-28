"""gm-llm — the command surface.

One CLI, two audiences. The top level is player-facing and ships in the wheel:

    gm-llm                      play the campaign in the current directory
    gm-llm play [dir]           --player human|auto  --ui tui|console  --mock  --setup
    gm-llm status [dir]         where the campaign stands (disk only, no model)
    gm-llm tokens [dir]         token + cost usage, read back from opencode's own store
    gm-llm init | update | doctor

The `dev` and `bench` groups are workshop surfaces and register **only when running from a
source checkout** (`_is_checkout`) — `bench` needs `dev/fixtures/`, which isn't packaged, so
registering it in an installed copy would only ever offer a command that can't work. From a
checkout, reach them with `python -m gm_llm dev …` / `python -m gm_llm bench …`, which runs
the checkout's code with no install step.

`play` keeps its three axes as flags rather than baking them into command names — who
supplies player turns, which frontend renders it, which backend answers. Command names for
combinations is how this surface previously grew five commands covering four of twelve
cells, with one exact duplicate. Combinations the code doesn't implement yet fail by name.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__


def _is_checkout() -> bool:
    """True when this package is being run out of the source tree (a sibling `dev/` next to
    the package dir), rather than from an installed wheel."""
    return (Path(__file__).resolve().parents[1] / "dev").is_dir()


# ── project commands ─────────────────────────────────────────────────────────

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


def _cmd_status(args) -> int:
    """Where the campaign stands — a renderer over `campaign_status()` (disk only, no
    server, no model). The TUI's status modal renders the same snapshot."""
    from .console import c
    from .orchestrator import campaign_status
    root = Path(args.dir)
    if not (root / "campaign").is_dir():
        print(f"campaign: {root}\nphase: no campaign yet — `gm-llm play` opens in setup")
        return 0
    st = campaign_status(root)
    print(f"campaign: {st.root}")
    print(f"phase: {'setup (no session planned yet)' if st.session is None else f'play · latest session: {st.session}'}")

    if st.session is not None:
        marks = [c("32", f"{name} ✓") if present else c("2", f"{name} ✗")
                 for name, present in st.artifacts]
        print(f"session {st.session}: " + " · ".join(marks))
        if st.reconcile_stages:
            print(f"reconcile {st.session}: {len(st.reconcile_stages)} stage(s) done "
                  f"({', '.join(st.reconcile_stages)})")

    line = f"entities: {st.entities_complete}/{st.entities_total} complete (lint)"
    hint = " — run `python -m gm_llm dev lint` for detail" if _is_checkout() else ""
    print(c("31", line + hint) if st.incomplete else c("32", line))

    if st.git_state is not None:
        state = "dirty (uncommitted campaign changes)" if st.git_state == "dirty" else "clean"
        print(f"git: {state}" + (f' · last: "{st.last_commit}"' if st.last_commit else ""))
    return 0


def _cmd_tokens(args) -> int:
    """Token + cost usage for any directory, read back out of opencode's own store. A batch
    dir (one holding `run-*` subdirs) groups per run and splits grading out; a plain
    campaign reports one set of per-agent totals."""
    import json

    from . import tokens as tok
    root = Path(args.dir)
    by_run = args.by_run or any(root.glob("run-*"))
    batch = (tok.usage_for_batch(root, data_dir=args.data_dir) if by_run
             else {"runs": {root.name or str(root): tok.usage_for(root, data_dir=args.data_dir)},
                   "grading": tok.Reading(), "out_dir": str(root)})
    if args.json:
        print(json.dumps({
            "out_dir": batch["out_dir"],
            "runs": {name: {"unavailable": r.unavailable, "total": vars(r.total),
                            "by_agent": {a: vars(u) for a, u in r.by_agent.items()}}
                     for name, r in batch["runs"].items()},
            "grading": {"unavailable": batch["grading"].unavailable,
                        "total": vars(batch["grading"].total)},
        }, ensure_ascii=False, indent=2))
        return 0
    prices = None
    if args.price_in is not None and args.price_out is not None:
        prices = (args.price_in, args.price_out, args.price_cache_read)
    elif args.price_in is not None or args.price_out is not None:
        print("--price-in and --price-out must be given together — skipping the cost table.",
              file=sys.stderr)
    print(tok.format_tokens(batch, prices=prices))
    return 0


# ── play: the three axes ─────────────────────────────────────────────────────

def run_play(args) -> int:
    """Dispatch on (player, ui, backend). Every supported combination routes to one
    implementation; unsupported ones name themselves rather than silently doing something
    adjacent. `dev autoplay` reaches this same function, so the two front doors onto
    `--player auto` can't drift."""
    player = getattr(args, "player", "human")
    ui = getattr(args, "ui", "tui")
    mock = getattr(args, "mock", False)

    if player == "auto" and mock:
        from .devcmds import unavailable
        unavailable("--player auto needs a real backend (the mock has no gate to score).")

    if player == "auto" and ui == "console":
        from . import autoplay
        return autoplay.run(args)          # exits via with_engine

    if ui == "console":
        from .devcmds import unavailable
        unavailable("a human-facing console frontend isn't implemented — the human "
                    "frontend is the TUI. Use `--ui tui` (the default).")

    # Both TUI cells, human and auto, are the same app over one session loop — the axis
    # is which `PlayerSource` the lifecycle hands it (design/frontends.md, step 2).
    return _launch_tui(args, mock=mock, player=player)


def _launch_tui(args, *, mock: bool, player: str = "human") -> int:
    """The Textual app, in-process. Live boots a real backend rooted at `dir`; mock runs
    against `MockLifecycle` so the UI can be worked on with no opencode and no rate limit."""
    from .tui.app import PlayApp

    if mock:
        from .orchestrator.mock import MockLifecycle
        app = PlayApp(MockLifecycle(start_in_setup=args.setup), cleanup=None, theme=args.theme)
        app.title = "gm-llm (MOCK)"
        app.run()
        return 0

    directory = Path(args.dir).resolve()
    if not (directory / ".opencode" / "agent").is_dir():
        print(f"no .opencode assets in {directory} — run `gm-llm init` here first.",
              file=sys.stderr)
        return 1

    from .orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
    from .orchestrator.logs import debug_enabled

    auto = player == "auto"
    # Read the packet before the screen is taken over — the resolver reports to stdout.
    character = ""
    if auto:
        from .autoplay import read_character
        character = read_character(str(directory), args.character)

    logs = Logs.under(project=directory, debug=debug_enabled())
    backend = Backend(str(directory), port=args.port, logs=logs).start()
    try:
        gate = Gate(backend, CanonPreloader(str(directory)), logs=logs)
        lifecycle = Lifecycle(backend, gate, str(directory), logs=logs,
                              player=player, character=character)
        app = PlayApp(lifecycle, cleanup=backend.stop, theme=args.theme,
                      turn_cap=args.turn_cap if auto else None)
        app.title = "gm-llm (live · autoplay)" if auto else "gm-llm (live)"
        app.run()
    finally:
        backend.stop()
    return 0


# ── parser ───────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gm-llm", description="An LLM game master for solo D&D campaigns, over opencode.")
    ap.add_argument("--version", action="version", version=f"gm-llm {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    # Two conventions, one rule: a top-level command takes the campaign as a positional
    # path (it's the thing you're acting on); a workshop command takes `--dir` (it's a
    # setting on a tool). The backend flags are declared once so the four hardcoded
    # 4181s that used to be spread across three CLIs can't drift again.
    backend_flags = argparse.ArgumentParser(add_help=False)
    backend_flags.add_argument("--port", type=int, default=4181)
    backend_flags.add_argument("--min-gap", type=float, default=1.0,
                               help="min seconds between any two model calls")
    backend_flags.add_argument("--stream", action="store_true",
                               help="stream the dm/checker output live as it generates (verbose)")
    backend_flags.add_argument("--turn-timeout", type=int, default=0,
                               help="per model-call timeout in seconds (0 = per-command "
                                    "default; play=360, prep/reconcile=1800)")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=".", help="campaign project directory (default: cwd)")

    engine = argparse.ArgumentParser(add_help=False, parents=[common, backend_flags])

    p = sub.add_parser("play", parents=[backend_flags],
                       help="play a campaign (the default command)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--player", choices=("human", "auto"), default="human",
                   help="who supplies player turns (default: human)")
    p.add_argument("--ui", choices=("tui", "console"), default="tui",
                   help="frontend (default: tui)")
    p.add_argument("--mock", action="store_true",
                   help="mock backend — no opencode, no rate limit (UI work)")
    p.add_argument("--setup", action="store_true",
                   help="with --mock: start in the new-campaign setup phase "
                        "(live detects this from disk)")
    p.add_argument("--theme", default="dracula",
                   help="Textual theme (dracula, tokyo-night, gruvbox, nord, …)")
    # autoplay's flags, accepted here too so `play --player auto` is the same command
    p.add_argument("--turn-cap", type=int, default=30, help=argparse.SUPPRESS)
    p.add_argument("--fresh", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--kickoff", default="Let's begin the session.", help=argparse.SUPPRESS)
    p.add_argument("--character", default=None, help=argparse.SUPPRESS)
    p.set_defaults(func=run_play)

    p = sub.add_parser("status", help="where the campaign stands (disk only, no model)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.set_defaults(func=_cmd_status)

    p = sub.add_parser("tokens", help="token + cost usage, read back from opencode's store")
    p.add_argument("dir", nargs="?", default=".",
                   help="campaign or batch directory (default: cwd)")
    p.add_argument("--by-run", action="store_true",
                   help="force per-run grouping (auto-detected when run-* dirs are present)")
    p.add_argument("--data-dir", default=None,
                   help="opencode data dir (default: $OPENCODE_DATA or ~/.local/share/opencode)")
    p.add_argument("--price-in", type=float, default=None, metavar="USD",
                   help="$ per million input tokens — enables the hypothetical cost table")
    p.add_argument("--price-out", type=float, default=None, metavar="USD",
                   help="$ per million output tokens")
    p.add_argument("--price-cache-read", type=float, default=0.0, metavar="USD",
                   help="$ per million cached-read tokens (default: 0)")
    p.add_argument("--json", action="store_true",
                   help="emit the machine-readable reading instead of the text report")
    p.set_defaults(func=_cmd_tokens)

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

    if _is_checkout():
        from .bench.cli import add_bench_parser
        from .devcmds import add_dev_parser
        add_dev_parser(sub, common, engine)
        add_bench_parser(sub, engine)

    return ap


def main(argv=None) -> int:
    if os.name == "nt":
        # Redirected/piped stdio on Windows defaults to the legacy ANSI code page
        # (cp1252), which can't encode ✓/✗ or the TUI's box-drawing characters —
        # force UTF-8 so output degrades to replacement chars instead of crashing.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass
    ap = _build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        # Bare `gm-llm` → play in the current directory (the primary use).
        args = ap.parse_args(["play"])
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
