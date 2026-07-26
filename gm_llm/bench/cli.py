"""
The `bench` CLI seam — mounted onto the main CLI's subparsers.

`gm_llm/cli.py` calls `add_bench_parser(sub, engine)` to graft the `bench` group onto the
CLI when it is running from a checkout (the fixtures under `dev/` aren't packaged, so an
installed copy has nothing to run). `engine` is the shared parent carrying `--dir` plus the
backend flags (`--port/--min-gap/--stream/--turn-timeout`), which `bench run` and
`bench grade` need. `bench run` plays a fixture into archives (B1); `bench grade` scores the
flagged violations in a batch's archives with the pinned grader model (B2); `bench report`
aggregates archives + grades into a summary with no model calls (B2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import grade, runner, scoring

# The fixtures live under dev/, resolved from this file's location so the default holds
# regardless of the invoker's cwd (bench/cli.py → gm_llm → repo root).
REPO = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO / "dev" / "fixtures" / "hollowfell"


def _note(msg: str) -> None:
    tty = sys.stdout.isatty()
    line = f"[bench] {msg}"
    print(f"\033[2m{line}\033[0m" if tty else line, flush=True)


def add_bench_parser(subparsers, engine) -> None:
    """Register the `bench` group and its sub-subcommands on `subparsers`. `engine` is the
    main CLI's shared parent parser (`--dir` + the backend flags)."""
    bench = subparsers.add_parser("bench", help="benchmark harness (BENCHMARK.md)")
    bsub = bench.add_subparsers(dest="bench_cmd", required=True)

    run = bsub.add_parser("run", parents=[engine],
                          help="play a fixture N times, condition-stamped, into --out")
    run.add_argument("--fixture", default=str(DEFAULT_FIXTURE),
                     help=f"fixture dir (default: {DEFAULT_FIXTURE})")
    run.add_argument("--runs", type=int, default=1, help="how many plays (default: 1)")
    run.add_argument("--turn-cap", type=int, default=50,
                     help="hard turn cap — the safety net past a natural wrap (default: 50)")
    run.add_argument("--play-only", action="store_true",
                     help="skip the post-session reconcile (cheap iteration)")
    run.add_argument("--resume", action="store_true",
                     help="continue incomplete runs in --out (rate-limited/crashed) in place, "
                          "instead of starting fresh ones (ignores --runs)")
    run.add_argument("--out", default="bench-out",
                     help="output dir for template + run dirs + batch.jsonl (default: bench-out)")
    run.add_argument("--kickoff", default="Let's begin the session.")
    run.set_defaults(func=cmd_bench_run)

    grade_p = bsub.add_parser("grade", parents=[engine],
                              help="grade the flagged violations in a batch's archives (B2)")
    grade_p.add_argument("--out", default="bench-out",
                         help="batch dir to grade (holds batch.jsonl + run dirs; default: bench-out)")
    grade_p.add_argument("--model", default=None,
                         help="override the pinned grader model (a V2 re-grade — grades are derived data)")
    grade_p.add_argument("--force", action="store_true",
                         help="re-grade runs already graded at this rubric+model")
    grade_p.add_argument("--double", action="store_true",
                         help="grade a sample twice in independent sessions and report agreement")
    grade_p.add_argument("--sample", type=int, default=None,
                         help="with --double: findings per run to re-grade (default: all)")
    grade_p.set_defaults(func=cmd_bench_grade)

    report_p = bsub.add_parser("report",
                               help="aggregate a batch's archives + grades into a summary (B2; no model calls)")
    report_p.add_argument("--out", default="bench-out",
                          help="batch dir to report on (default: bench-out)")
    report_p.add_argument("--json", action="store_true",
                          help="emit the machine-readable summary instead of the text report")
    report_p.set_defaults(func=cmd_bench_report)



def cmd_bench_run(args) -> None:
    """Translate the parsed args into a `run_batch` call. Reconcile is a long between-
    session dm pass, so the per-call timeout defaults generous (1800s) unless the run is
    play-only or the user overrode `--turn-timeout`."""
    timeout = args.turn_timeout or (360 if args.play_only else 1800)
    mode = "resume" if args.resume else f"runs={args.runs}"
    _note(f"fixture={args.fixture} {mode} out={args.out} "
          f"turn-cap={args.turn_cap} reconcile={not args.play_only}")
    records = runner.run_batch(
        args.fixture, args.out, runs=args.runs, turn_cap=args.turn_cap,
        play_only=args.play_only, kickoff=args.kickoff, resume=args.resume, port=args.port,
        min_gap=args.min_gap, turn_timeout=timeout, stream=args.stream, note=_note)

    done = sum(1 for r in records if r["outcome"] == "complete")
    capped = sum(1 for r in records if r["outcome"] == "cap")
    incomplete = sum(1 for r in records if str(r["outcome"]).startswith("incomplete"))
    failed = sum(1 for r in records if str(r["outcome"]).startswith("failed"))
    tail = " — resume with `python -m gm_llm bench run --resume`" if incomplete else ""
    _note(f"batch done: {done} complete · {capped} capped · {incomplete} incomplete · "
          f"{failed} failed → {Path(args.out) / 'batch.jsonl'}{tail}")
    sys.exit(1 if failed and not done else 0)


def cmd_bench_grade(args) -> None:
    """Grade every archive in `--out` with the pinned grader (`--model` overrides for a V2
    re-grade). The grader is a between-run scoring pass, not a play turn, so the per-call
    timeout defaults generous (600s) unless the user overrode `--turn-timeout`."""
    timeout = args.turn_timeout or 600
    _note(f"grading out={args.out} model={args.model or '(pinned)'} "
          f"force={args.force} double={args.double}")
    result = grade.grade_batch(
        args.out, model=args.model, force=args.force, double=args.double,
        sample=args.sample, port=args.port, min_gap=args.min_gap, turn_timeout=timeout,
        note=_note)
    _note(f"graded {len(result['graded'])} run(s).")
    if result.get("double"):
        d = result["double"]
        if d["n"]:
            _note(f"agreement (n={d['n']}): severity {d['severity_match']:.0%}, "
                  f"category {d['category_match']:.0%}")
    sys.exit(0)


def cmd_bench_report(args) -> None:
    """Aggregate `--out`'s archives + grades and print the report (or `--json`). No model
    calls — pure re-derivation from the raw archive and the derived grades."""
    batch = scoring.summarize_batch(args.out)
    if args.json:
        print(json.dumps(batch, ensure_ascii=False, indent=2))
    else:
        print(scoring.format_report(batch))
    sys.exit(0)

