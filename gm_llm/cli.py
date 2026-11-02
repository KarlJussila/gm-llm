"""gm-llm — the command surface.

One CLI, two audiences. The top level is player-facing and ships in the wheel:

    gm-llm                      play the campaign in the current directory
    gm-llm play [dir]           --player human|auto  --ui tui|console  --mock  --setup
    gm-llm serve [dir]          the engine over stdio, for a frontend to drive
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

def _cmd_init(args) -> int:
    from .project import init_project
    dest = init_project(Path(args.dir), force=args.force)
    print(f"initialized opencode assets in {dest}")
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
    print("your campaign/ data, gm-llm.yaml settings and .orchestrator markers were left untouched.")
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


def _session_timeline(tok, root: Path, args) -> int:
    """`tokens --sessions` / `--session N`: the per-session list, or one session step by step."""
    sessions, reason = tok.sessions_for(root, data_dir=args.data_dir)
    if reason:
        print(f"token data unavailable: {reason}", file=sys.stderr)
        return 1
    if not args.session:
        print(tok.format_sessions(root, sessions))
        return 0
    sid = tok.resolve(sessions, args.session)
    if not sid:
        print(f"no single session matches {args.session!r} under {root}", file=sys.stderr)
        return 1
    print(tok.format_timeline(sid, data_dir=args.data_dir, reasoning=args.reasoning,
                              width=args.width))
    return 0


def _cmd_tokens(args) -> int:
    """Token + cost usage for any directory, read back out of opencode's own store. A batch
    dir (one holding `run-*` subdirs) groups per run and splits checking and grading out; a
    plain campaign reports one set of per-agent totals."""
    import json

    from . import tokens as tok
    root = Path(args.dir)
    if args.sessions or args.session:
        return _session_timeline(tok, root, args)
    by_run = args.by_run or any(root.glob("run-*"))
    batch = (tok.usage_for_batch(root, data_dir=args.data_dir) if by_run
             else {"runs": {root.name or str(root): tok.usage_for(root, data_dir=args.data_dir)},
                   "checking": tok.Reading(), "grading": tok.Reading(), "out_dir": str(root)})
    if args.json:
        print(json.dumps({
            "out_dir": batch["out_dir"],
            "runs": {name: {"unavailable": r.unavailable, "total": vars(r.total),
                            "by_agent": {a: vars(u) for a, u in r.by_agent.items()}}
                     for name, r in batch["runs"].items()},
            **{scope: {"unavailable": batch[scope].unavailable, "total": vars(batch[scope].total)}
               for scope in ("checking", "grading")},
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
    if getattr(args, "sessions", None) is not None and player != "auto":
        print("--sessions needs --player auto", file=sys.stderr)
        return 2

    script = getattr(args, "setup_script", None)
    if script:
        if mock:
            from .devcmds import unavailable
            unavailable("--setup-script needs a real backend.")
        from .orchestrator.autosetup import SetupScriptError, load_script
        try:
            load_script(script)
        except SetupScriptError as e:
            print(e, file=sys.stderr)
            return 1
        # A scripted setup starts from nothing: scaffold a fresh directory's assets here.
        if not (Path(args.dir).resolve() / ".opencode" / "agent").is_dir():
            from .project import init_project
            print(f"initialized opencode assets in {init_project(Path(args.dir))}")

    if ui == "console":
        return _run_console(args)

    # Both TUI cells, human and auto, are the same app over one session loop — the axis
    # is which `PlayerSource` the lifecycle hands it (design/frontends.md, step 2).
    return _launch_tui(args, mock=mock, player=player)


def _serve_args(args) -> list[str]:
    """`play`'s flags as `gm-llm serve` takes them — what a frontend spawns its engine with."""
    out = [str(Path(args.dir).resolve()), "--player", getattr(args, "player", "human"),
           "--port", str(args.port), "--min-gap", str(args.min_gap),
           "--turn-timeout", str(args.turn_timeout)]
    if args.mock:
        out += ["--mock"] + (["--setup"] if args.setup else [])
    if args.model is not None:
        out += ["--model", args.model]
    if args.variant is not None:
        out += ["--variant", args.variant]
    if getattr(args, "turn_cap", None) is not None:
        out += ["--turn-cap", str(args.turn_cap)]
    if getattr(args, "sessions", None) is not None:
        out += ["--sessions", str(args.sessions)]
    if getattr(args, "fresh", False):
        out += ["--fresh"]
    if getattr(args, "setup_script", None):
        out += ["--setup-script", str(Path(args.setup_script).expanduser().resolve())]
    return out


def _has_assets(args) -> bool:
    directory = Path(args.dir).resolve()
    if args.mock or (directory / ".opencode" / "agent").is_dir():
        return True
    print(f"no .opencode assets in {directory} — run `gm-llm init` here first.",
          file=sys.stderr)
    return False


def _run_console(args) -> int:
    from . import consoleui
    from .engine.client import ProcessClient
    if not _has_assets(args):
        return 1
    return consoleui.run(ProcessClient(["serve", *_serve_args(args)]), stream=args.stream)


def _cmd_serve(args) -> int:
    from .engine.serve import claim_stdout, fail, serve
    out = claim_stdout()
    try:
        from .engine.core import open_engine
        engine = open_engine(args.dir, player=args.player, model=args.model,
                             variant=args.variant, port=args.port, min_gap=args.min_gap,
                             turn_timeout=args.turn_timeout, turn_cap=args.turn_cap,
                             fresh=args.fresh, mock=args.mock, setup=args.setup,
                             setup_script=args.setup_script, sessions=args.sessions)
    except Exception as e:  # noqa: BLE001 — the frontend shows it
        return fail(out, str(e))
    return serve(engine, out)


def _launch_tui(args, *, mock: bool, player: str = "human") -> int:
    """The Textual app over a `gm-llm serve` child. The engine's stderr goes to a log file:
    the terminal belongs to Textual."""
    import tempfile

    from .engine.client import ProcessClient
    from .tui.app import PlayApp

    if not _has_assets(args):
        return 1
    if mock:
        log_dir = Path(tempfile.gettempdir())
    else:
        log_dir = Path(args.dir).resolve() / ".opencode" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "engine.log", "w", encoding="utf-8") as log:
        client = ProcessClient(["serve", *_serve_args(args)], stderr=log)
        app = PlayApp(client, theme=getattr(args, "theme", "dracula"))
        app.title = ("gm-llm (MOCK)" if mock else
                     "gm-llm (live · autoplay)" if player == "auto" else "gm-llm (live)")
        try:
            app.run()
        finally:
            client.close()
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
                               help="per model-call timeout in seconds (0 = the command's "
                                    "default: 1800; bench check/grade 600, a play-only bench "
                                    "run 360)")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=".", help="campaign project directory (default: cwd)")

    engine = argparse.ArgumentParser(add_help=False, parents=[common, backend_flags])

    # The campaign's model for one invocation, over gm-llm.yaml's. The bench sets its own
    # (`--subject-model`).
    model_flags = argparse.ArgumentParser(add_help=False)
    model_flags.add_argument("--model", default=None, metavar="PROVIDER/MODEL",
                             help="run every agent but the AI players on this model "
                                  "(over gm-llm.yaml's model)")
    model_flags.add_argument("--variant", default=None,
                             help="reasoning variant ('' for none; default: none with --model, "
                                  "else gm-llm.yaml's or each agent's own)")

    p = sub.add_parser("play", parents=[backend_flags, model_flags],
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
    p.add_argument("--setup-script", default=None, metavar="FILE",
                   help="a new campaign: a scripted player answers setup from FILE "
                        "(see README § Scripted setup)")
    p.add_argument("--theme", default="dracula",
                   help="Textual theme (dracula, tokyo-night, gruvbox, nord, …)")
    p.add_argument("--sessions", type=int, default=None, metavar="N",
                   help="with --player auto: stop after playing N sessions (default: no limit)")
    p.add_argument("--turn-cap", type=int, default=None, metavar="N",
                   help="with --player auto: pause a session after N turns (default: no limit)")
    # `dev autoplay`'s flag, accepted here too so `play --player auto` is the same command
    p.add_argument("--fresh", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=run_play)

    p = sub.add_parser("serve", parents=[backend_flags, model_flags],
                       help="the engine over stdio, for a frontend to drive")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--player", choices=("human", "auto"), default="human")
    p.add_argument("--turn-cap", type=int, default=None,
                   help="stop an agent-played session after this many turns")
    p.add_argument("--sessions", type=int, default=None,
                   help="with --player auto: stop after playing this many sessions")
    p.add_argument("--mock", action="store_true", help="mock backend — no opencode")
    p.add_argument("--setup", action="store_true",
                   help="with --mock: start in the new-campaign setup phase")
    p.add_argument("--fresh", action="store_true",
                   help="open the session over instead of resuming its transcript")
    p.add_argument("--setup-script", default=None, metavar="FILE",
                   help="a scripted player answers setup from FILE")
    p.set_defaults(func=_cmd_serve)

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
    p.add_argument("--sessions", action="store_true",
                   help="list every session instead: wall and model time, steps, peak context, "
                        "skills loaded")
    p.add_argument("--session", default=None, metavar="N|ID",
                   help="print one session step by step — its number in --sessions, or an id prefix")
    p.add_argument("--reasoning", action="store_true",
                   help="with --session: include the reasoning headings")
    p.add_argument("--width", type=int, default=600,
                   help="with --session: cap each text block at this many chars (0: no cap)")
    p.set_defaults(func=_cmd_tokens)

    p = sub.add_parser("init", help="scaffold opencode assets into a project")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--force", action="store_true", help="overwrite existing assets")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("update", help="refresh an existing project's framework assets to this version")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.set_defaults(func=_cmd_update)

    p = sub.add_parser("doctor", help="check the environment (opencode, runtime, port)")
    p.add_argument("dir", nargs="?", default=".", help="project directory (default: cwd)")
    p.add_argument("--port", type=int, default=4181)
    p.set_defaults(func=_cmd_doctor)

    if _is_checkout():
        from .bench.cli import add_bench_parser
        from .devcmds import add_dev_parser
        add_dev_parser(sub, common,
                       argparse.ArgumentParser(add_help=False, parents=[engine, model_flags]))
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
