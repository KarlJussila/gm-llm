"""
The `bench` CLI seam — mounted onto `dev/cli.py`'s subparsers.

`dev/cli.py` calls `add_bench_parser(sub, common)` to graft the `bench` command (and its
sub-subcommands) onto the dev control CLI, passing its shared `common` parent so the
backend flags (`--port/--min-gap/--stream/--turn-timeout`) apply to `bench run`.
`bench run` plays a fixture into archives (B1); `bench grade` and `bench report` follow
in B2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import runner

# The fixtures live under dev/, resolved from this file's location so the default holds
# regardless of the invoker's cwd (bench/cli.py → gm_llm → repo root).
REPO = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO / "dev" / "fixtures" / "hollowfell"


def _note(msg: str) -> None:
    tty = sys.stdout.isatty()
    line = f"[bench] {msg}"
    print(f"\033[2m{line}\033[0m" if tty else line, flush=True)


def add_bench_parser(subparsers, common) -> None:
    """Register the `bench` subcommand and its sub-subcommands on `subparsers`. `common`
    is dev/cli.py's shared backend-flags parent parser."""
    bench = subparsers.add_parser("bench", help="benchmark harness (BENCHMARK.md)")
    bsub = bench.add_subparsers(dest="bench_cmd", required=True)

    run = bsub.add_parser("run", parents=[common],
                          help="play a fixture N times, condition-stamped, into --out")
    run.add_argument("--fixture", default=str(DEFAULT_FIXTURE),
                     help=f"fixture dir (default: {DEFAULT_FIXTURE})")
    run.add_argument("--runs", type=int, default=1, help="how many plays (default: 1)")
    run.add_argument("--turn-cap", type=int, default=30,
                     help="hard turn cap — the safety net past a natural wrap (default: 30)")
    run.add_argument("--play-only", action="store_true",
                     help="skip the post-session reconcile (cheap iteration)")
    run.add_argument("--out", default="bench-out",
                     help="output dir for template + run dirs + batch.jsonl (default: bench-out)")
    run.add_argument("--kickoff", default="Let's begin the session.")
    run.set_defaults(func=cmd_bench_run)


def cmd_bench_run(args) -> None:
    """Translate the parsed args into a `run_batch` call. Reconcile is a long between-
    session dm pass, so the per-call timeout defaults generous (1800s) unless the run is
    play-only or the user overrode `--turn-timeout`."""
    timeout = args.turn_timeout or (360 if args.play_only else 1800)
    _note(f"fixture={args.fixture} runs={args.runs} out={args.out} "
          f"turn-cap={args.turn_cap} reconcile={not args.play_only}")
    records = runner.run_batch(
        args.fixture, args.out, runs=args.runs, turn_cap=args.turn_cap,
        play_only=args.play_only, kickoff=args.kickoff, port=args.port,
        min_gap=args.min_gap, turn_timeout=timeout, stream=args.stream, note=_note)

    done = sum(1 for r in records if r["outcome"] == "complete")
    capped = sum(1 for r in records if r["outcome"] == "cap")
    failed = sum(1 for r in records if str(r["outcome"]).startswith("failed"))
    _note(f"batch done: {done} complete · {capped} capped · {failed} failed "
          f"→ {Path(args.out) / 'batch.jsonl'}")
    sys.exit(1 if failed and not done else 0)
