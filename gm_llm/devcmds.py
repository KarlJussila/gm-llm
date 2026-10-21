"""
The `dev` command group — the workshop surface over the orchestrator core.

These are the commands you run *on* a campaign rather than *in* one: re-author a plan out
of band, finish a reconcile that died partway, lint entity files, probe the rate limit.
They register only when the CLI is running from a source checkout (see
`cli._is_checkout`), because that is the only place they're meant to be used — a campaign
reaching them from an installed `gm-llm` would be a sign something went wrong, not a
feature.

`reconcile` in particular is here and not on the player surface deliberately. The
lifecycle already decides from disk whether a campaign should be playing or reconciling
(`Lifecycle.__init__`), and the TUI drives the post-session pipeline itself. Running it by
hand applies a non-idempotent canon pass plus two commits *outside* that state machine — a
repair tool for someone who knows why they're reaching for it, not a recovery button.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import autoplay
from .console import banner, c, fail, note, sessions_dir, show_prep, verdict, with_engine
from .orchestrator import Planner, Reconciler
from .orchestrator import paths
from .orchestrator.paths import latest_session

_PING_MODEL = os.environ.get("MODEL", "openai/gpt-6-luna")
_PING_TIMEOUT = int(os.environ.get("TIMEOUT", "45"))


def _pick_session(args, *, next_session: bool) -> int:
    """Resolve --session, defaulting from disk: prep targets the session after the latest
    plan; reconcile targets the latest *played* session (highest transcript — after a full
    wrap the newest plan is the unplayed N+1). Prints what was inferred so a default never
    runs silently against the wrong session."""
    import re
    if args.session:
        return args.session
    if next_session:
        n = (latest_session(Path(args.dir) / "campaign") or 0) + 1
        note(f"--session not given — prepping the next session: {n}")
        return n
    played = [int(d.name) for d in sessions_dir(args.dir).glob("*")
              if d.name.isdigit() and paths.transcript(Path(args.dir) / "campaign", int(d.name)).is_file()]
    if not played:
        fail("no play transcripts on disk — nothing to reconcile (play a session first)")
        sys.exit(2)
    n = max(played)
    note(f"--session not given — reconciling the latest played session: {n}")
    return n


def cmd_prep(args):
    def body(backend, gate, logs):
        n = _pick_session(args, next_session=True)
        note(f"prepping session {n} — the dm authors, then the gate runs…")
        pr = Planner(backend, gate, logs=logs).prep_session(n, commit=args.commit)
        print(flush=True)
        show_prep(pr, show_report=not args.stream)

    with_engine(args, body, default_timeout=1800)


def cmd_reconcile(args):
    def body(backend, gate, logs):
        n = _pick_session(args, next_session=False)
        note(f"reconciling session {n} — staged apply, gated stage by stage…")
        rr = Reconciler(backend, gate, logs=logs).reconcile_session(
            n, commit=args.commit, prep=not args.no_prep, fresh=args.fresh)

        print(flush=True)
        for label, g in (("check-digest", rr.digest), ("check-propagation", rr.propagation)):
            if g is not None:  # None = stage skipped this run (resumed past it)
                verdict(label, g.narrative, show_report=not args.stream)
        if rr.lint_incomplete:
            print(c("33", f"┄┄ canon lint: {rr.lint_incomplete} issue(s) · "
                          f"correction dispatched ┄┄"), flush=True)
        if rr.arcs_missed:
            print(c("33", f"┄┄ arcs unstamped after the pass: {', '.join(rr.arcs_missed)} · "
                          f"nudge sent ┄┄"), flush=True)
        banner(f"session {rr.n} reconciled{' · committed' if rr.committed else ''}")
        if rr.prep is not None:
            show_prep(rr.prep, show_report=not args.stream)

    with_engine(args, body, default_timeout=1800)


def cmd_lint(args):
    """The canon lint — no backend, no model calls. Refreshes INDEX.md and the reveal flags
    first, the same as the orchestrator does before it lints."""
    from .orchestrator.lint import lint_campaign
    from .orchestrator.phase import refresh_campaign
    refresh_campaign(args.dir)
    issues = lint_campaign(args.dir)
    for i in issues:
        print(c("31", f"  ✗ {i.rel}  {i.message}"))
    print(c("1;36" if not issues else "1;31", f"\n━━ canon lint: {len(issues)} issue(s) ━━"))
    sys.exit(1 if issues else 0)


def cmd_ping(args):
    """Is the model answering, or still rate-limited?

    A throttled call to the free tier *hangs* rather than erroring (hence the
    orchestrator's long turn_timeout), so a one-shot `opencode run` gets a hard timeout and
    the timeout itself is the signal. It runs on a private server from a neutral dir, so it
    probes only the model/account quota, which is per-account, not per-project.

    A single ping clearing doesn't prove sustained throughput — a full autoplay or
    benchmark burst can re-trip a rolling-window limit even when one shot succeeds."""
    rc = 0
    for i in range(1, args.count + 1):
        if args.count > 1:
            print(f"probe {i}/{args.count}:", end="", flush=True)
        try:
            p = subprocess.run(
                ["opencode", "run", "--standalone", "-m", args.model, "Reply with exactly: OK"],
                cwd="/tmp", capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(c("31", f"  STILL THROTTLED — call hung past {args.timeout}s"), flush=True)
            rc = 124
            continue
        except FileNotFoundError:
            fail("opencode not on PATH")
            sys.exit(127)
        if p.returncode == 0:
            print(c("32", f"  cleared — model replied ({args.model})"), flush=True)
        else:
            tail = (p.stderr or p.stdout or "").strip().splitlines()
            print(c("31", f"  errored (exit {p.returncode}): {tail[-1] if tail else ''}"),
                  flush=True)
            rc = p.returncode
    sys.exit(rc)


def add_dev_parser(subparsers, common, engine) -> None:
    """Register the `dev` group. `common` carries `--dir`; `engine` adds the backend flags
    on top, for the commands that call a model."""
    dev = subparsers.add_parser("dev", help="workshop commands over the orchestrator core")
    sub = dev.add_subparsers(dest="dev_cmd", required=True)

    p = sub.add_parser("autoplay", parents=[engine],
                       help="play a session with the scripted player agent (no human)")
    p.add_argument("--turn-cap", type=int, default=30,
                   help="stop after this many turns — play ends earlier when the runner "
                        "wraps the session (default: 30)")
    p.add_argument("--fresh", action="store_true",
                   help="start the session over, overwriting its transcript "
                        "(the default resumes an in-progress session)")
    p.add_argument("--kickoff", default="Let's begin the session.")
    p.add_argument("--character", default=None,
                   help="player packet injected into the player's first message "
                        "(default: auto-discover *.player.md at the project root; "
                        "'' to run blind)")
    p.add_argument("--ui", choices=("console", "tui"), default="console",
                   help="frontend to watch it through (default: console)")
    p.set_defaults(func=lambda a: _autoplay(a))

    p = sub.add_parser("prep", parents=[engine],
                       help="PRE: author + gate + commit a session plan, out of band")
    p.add_argument("--session", type=int, default=0, help="session to prep (default: next)")
    p.add_argument("--no-commit", dest="commit", action="store_false",
                   help="dry run — skip the git commit")
    p.set_defaults(func=cmd_prep)

    p = sub.add_parser("reconcile", parents=[engine],
                       help="POST: run the staged post-session pipeline by hand (repair)")
    p.add_argument("--session", type=int, default=0,
                   help="session to reconcile (default: latest played)")
    p.add_argument("--no-commit", dest="commit", action="store_false",
                   help="dry run — skip the git commits")
    p.add_argument("--no-prep", action="store_true", help="skip prepping session N+1")
    p.add_argument("--fresh", action="store_true",
                   help="clear stage markers and re-run from scratch")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("lint", parents=[common],
                       help="run the canon lint (frontmatter, links, secrets, state files)")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("ping", help="probe the model's rate-limit state")
    p.add_argument("count", nargs="?", type=int, default=1,
                   help="number of back-to-back probes (truer signal than one)")
    p.add_argument("--model", default=_PING_MODEL, help=f"model to probe (default: {_PING_MODEL})")
    p.add_argument("--timeout", type=int, default=_PING_TIMEOUT,
                   help=f"seconds before a hang counts as throttled (default: {_PING_TIMEOUT})")
    p.set_defaults(func=cmd_ping)


def _autoplay(args):
    """`dev autoplay` — the same driver `play --player auto` reaches, so the two front
    doors can never drift."""
    from .cli import run_play
    args.player = "auto"
    args.mock = False
    args.setup = False
    run_play(args)


def unavailable(what: str) -> None:
    """A frontend × player-mode combination the code doesn't implement yet. Named
    explicitly rather than silently falling back to something adjacent — a benchmark harness
    that quietly ran a different mode than asked for would be worse than an error."""
    fail(what)
    sys.exit(2)
