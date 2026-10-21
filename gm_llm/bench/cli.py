"""
The `bench` CLI seam — mounted onto the main CLI's subparsers.

`gm_llm/cli.py` calls `add_bench_parser(sub, engine)` to graft the `bench` group onto the
CLI when it is running from a checkout (the fixtures under `dev/` aren't packaged, so an
installed copy has nothing to run). `engine` is the shared parent carrying `--dir` plus the
backend flags (`--port/--min-gap/--stream/--turn-timeout`), which the model-calling commands
need. `bench run` plays a fixture into archives, `bench check` finds each turn's mistakes,
`bench grade` confirms or rejects and grades them, and `bench report` and `bench status`
aggregate with no model calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import check, grade, runner, scoring

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
    bench = subparsers.add_parser("bench", help="benchmark harness (design/benchmark.md)")
    bsub = bench.add_subparsers(dest="bench_cmd", required=True)

    run = bsub.add_parser("run", parents=[engine],
                          help="play a fixture N times, condition-stamped, into --out")
    run.add_argument("--fixture", default=str(DEFAULT_FIXTURE),
                     help=f"fixture dir (default: {DEFAULT_FIXTURE})")
    run.add_argument("--runs", type=int, default=1, help="how many plays (default: 1)")
    run.add_argument("--tier", choices=runner.TIERS, default="low",
                     help="the scaffolding tier to play (default: low, the product)")
    run.add_argument("--subject-model", default=None,
                     help="run the subject agents (dm-runner, dm, author, log-extractor) on "
                          "this model instead of their pinned one")
    run.add_argument("--subject-variant", default=None,
                     help="the subject agents' reasoning variant ('' for none)")
    run.add_argument("--turn-cap", type=int, default=50,
                     help="hard turn cap — the safety net past a natural wrap (default: 50)")
    run.add_argument("--play-only", action="store_true",
                     help="skip the post-session reconcile (cheap iteration)")
    run.add_argument("--resume", action="store_true",
                     help="continue incomplete runs in --out (rate-limited/crashed) in place, "
                          "instead of starting fresh ones (ignores --runs)")
    run.add_argument("--out", default="bench-out",
                     help="output dir for template + run dirs + batch.jsonl (default: bench-out)")
    run.add_argument("--ui", choices=("console", "tui"), default="console",
                     help="watch the batch in the play TUI instead of streaming notes to "
                          "stdout (read-only; the archives are unaffected)")
    run.add_argument("--kickoff", default="Let's begin the session.")
    run.set_defaults(func=cmd_bench_run)

    check_p = bsub.add_parser("check", parents=[engine],
                              help="check each run's turns after play, one rolling session per run")
    check_p.add_argument("--out", default="bench-out",
                         help="batch dir to check (default: bench-out)")
    check_p.add_argument("--model", default=None,
                         help="override the checker's pinned model (checks are derived data)")
    check_p.add_argument("--force", action="store_true",
                         help="re-check runs already checked with this checker and instrument")
    check_p.set_defaults(func=cmd_bench_check)

    grade_p = bsub.add_parser("grade", parents=[engine],
                              help="confirm or reject and grade a checked batch's findings")
    grade_p.add_argument("--out", default="bench-out",
                         help="batch dir to grade (holds batch.jsonl + run dirs; default: bench-out)")
    grade_p.add_argument("--model", default=None,
                         help="override the pinned grader model (grades are derived data)")
    grade_p.add_argument("--force", action="store_true",
                         help="re-grade runs already graded with this instrument")
    grade_p.add_argument("--double", action="store_true",
                         help="grade a sample again in a second session and report agreement")
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

    status_p = bsub.add_parser("status", help="each run in a batch by outcome (no model calls)")
    status_p.add_argument("--out", default="bench-out",
                          help="batch dir to read (default: bench-out)")
    status_p.set_defaults(func=cmd_bench_status)



def _watch_in_tui(args, batch_kwargs) -> list:
    """`--ui tui`: the same batch, rendered in the play TUI instead of as stdout notes.

    `run_batch` stays where it is — the app drives it on its own thread and attaches to each
    run's lifecycle through `BatchHooks`, so what lands in the archives is what a headless
    batch lands (design/frontends.md § Constraints). Two consequences worth naming:

      * `--stream` is dropped — the behind-the-screen pane *is* the stream, and a second
        EventTap would write into a screen Textual owns.
      * The batch outlives the screen by design. Quitting stops the loop, and this joins the
        batch thread afterwards so the run in flight finishes unwinding (its backend
        stopped, its manifest line written) before the summary is printed."""
    from ..tui.app import PlayApp
    if args.stream:
        _note("--stream is what --ui tui already does (ctrl+g for the pane) — ignoring it.")
    records: list = []

    def drive(hooks):
        records.extend(runner.run_batch(args.fixture, args.out, hooks=hooks,
                                        note=app.note, **batch_kwargs))

    app = PlayApp(batch=drive)
    app.title = "gm-llm (bench)"
    app.run()
    if app.batch_running():
        _note("stopping — letting the run in flight unwind (backend, manifest)…")
    app.join_batch()
    return records


def cmd_bench_run(args) -> None:
    """Translate the parsed args into a `run_batch` call. Reconcile is a long between-
    session dm pass, so the per-call timeout defaults generous (1800s) unless the run is
    play-only or the user overrode `--turn-timeout`."""
    timeout = args.turn_timeout or (360 if args.play_only else 1800)
    mode = "resume" if args.resume else f"runs={args.runs}"
    _note(f"fixture={args.fixture} {mode} out={args.out} ui={args.ui} "
          f"turn-cap={args.turn_cap} reconcile={not args.play_only}")
    kw = dict(runs=args.runs, tier=args.tier, subject_model=args.subject_model,
              subject_variant=args.subject_variant, turn_cap=args.turn_cap,
              play_only=args.play_only,
              kickoff=args.kickoff, resume=args.resume, port=args.port,
              min_gap=args.min_gap, turn_timeout=timeout)
    records = (_watch_in_tui(args, kw) if args.ui == "tui"
               else runner.run_batch(args.fixture, args.out, stream=args.stream,
                                     note=_note, **kw))

    done = sum(1 for r in records if r["outcome"] == "complete")
    capped = sum(1 for r in records if r["outcome"] == "cap")
    incomplete = sum(1 for r in records if str(r["outcome"]).startswith("incomplete"))
    failed = sum(1 for r in records if str(r["outcome"]).startswith("failed"))
    pending = sum(1 for r in records if r["outcome"] == "complete" and r.get("archive")
                  and runner.reconcile_pending(Path(args.out) / r["archive"]))
    tail = (" — resume with `python -m gm_llm bench run --resume`"
            if incomplete or pending else "")
    held = f" ({pending} reconcile pending)" if pending else ""
    _note(f"batch done: {done} complete{held} · {capped} capped · {incomplete} incomplete · "
          f"{failed} failed → {Path(args.out) / 'batch.jsonl'}{tail}")
    # Non-zero unless every run finished, so `bench run && bench check` stops at a stopped run.
    sys.exit(1 if incomplete or failed or pending else 0)


def cmd_bench_check(args) -> None:
    """Check every run in `--out` with the after-play checker. A whole session's turns go
    through one session per run, so the per-call timeout defaults generous (600s)."""
    _note(f"checking out={args.out} model={args.model or '(pinned)'} force={args.force}")
    written = check.check_batch(args.out, model=args.model, force=args.force, port=args.port,
                                min_gap=args.min_gap, turn_timeout=args.turn_timeout or 600,
                                note=_note)
    _note(f"checked {len(written)} run(s).")
    sys.exit(0)


def cmd_bench_grade(args) -> None:
    """Grade every checked run in `--out` with the pinned grader (`--model` overrides)."""
    _note(f"grading out={args.out} model={args.model or '(pinned)'} "
          f"force={args.force} double={args.double}")
    result = grade.grade_batch(
        args.out, model=args.model, force=args.force, double=args.double,
        sample=args.sample, port=args.port, min_gap=args.min_gap,
        turn_timeout=args.turn_timeout or 600, note=_note)
    _note(f"graded {len(result['graded'])} run(s).")
    d = result.get("double")
    if d and d["n"]:
        line = f"agreement (n={d['n']}): verdict {d['verdict_match']:.0%}"
        if d["confirmed_both"]:
            line += (f"; over {d['confirmed_both']} confirmed by both, severity "
                     f"{d['severity_match']:.0%}, category {d['category_match']:.0%}")
        _note(line)
    sys.exit(0)


def cmd_bench_status(args) -> None:
    """Print the batch's runs grouped by where they stand."""
    status = runner.batch_status(args.out)
    if not status:
        print(f"no batch.jsonl under {args.out}")
        sys.exit(0)
    for state in ("complete", "reconcile pending", "resumable", "capped", "empty"):
        runs = status.get(state, [])
        if runs:
            print(f"{state} ({len(runs)}):")
            for rd in runs:
                print(f"  {rd}")
    if status.get("resumable") or status.get("reconcile pending"):
        print("resume with `python -m gm_llm bench run --resume`")
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

