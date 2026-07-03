#!/usr/bin/env python3
"""
gm-llm — orchestrator control CLI.

The developer control surface over the orchestrator core (`Game`, `Planner`,
`Reconciler`); the player's surface is the TUI. Every subcommand is a thin
front-end — the determinism lives in the library, not here.

    python .opencode/dev/cli.py status                 where the campaign stands (no model)
    python .opencode/dev/cli.py play      [--turns 6] [--resume]
    python .opencode/dev/cli.py prep      [--session N] [--no-commit]
    python .opencode/dev/cli.py reconcile [--session N] [--no-commit] [--no-prep] [--fresh]
    python .opencode/dev/cli.py tui       [--live] [--setup] [--theme tokyo-night]
    python .opencode/dev/cli.py lint      [--dir ...]
    python .opencode/dev/cli.py ping      [N]

Defaults do the right thing: `prep` targets the next session, `reconcile` the
latest played one (both inferred from disk, printed before running), and both
commit — pass `--no-commit` for a dry run. `play` drives the gated loop with
the scripted `player` agent; `--resume` continues the latest session from its
transcript. Ctrl-C stops any mode and shuts the server down.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEV = Path(__file__).resolve().parent
ROOT = DEV.parents[1]               # project root (campaign dir's parent of .opencode)
OPENCODE = DEV.parent               # the .opencode dir
sys.path.insert(0, str(OPENCODE))   # put .opencode on the path
from orchestrator import (  # noqa: E402
    Backend, BackendError, CanonPreloader, Gate, Game, Logs, Planner, Reconciler,
    campaign_status,
)
from orchestrator.canon import latest_session  # noqa: E402
from orchestrator.stream import EventTap  # noqa: E402

# Every log the orchestrator writes lives under one object (see orchestrator/logs.py):
# the serve/raw/checks/detail files, wired once and threaded to Backend, Gate, and the
# lifecycle. ORCH_DEBUG=1 turns on the raw per-reply dump.
LOGS = Logs.under(project=ROOT, debug=bool(os.environ.get("ORCH_DEBUG")))


# ─────────────────────────────── output ────────────────────────────────────
# One tiny vocabulary, used by every command: note/warn/fail for harness chatter,
# banner for the big beats, verdict for gate results. All colour goes through c().

_COLOR = sys.stdout.isatty()


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def note(msg):
    print(c("2", f"[harness] {msg}"), flush=True)


def warn(msg):
    print(c("33", f"[harness] {msg}"), flush=True)


def fail(msg):
    print(c("1;31", f"[harness] {msg}"), flush=True)


def banner(msg):
    print(c("1;36", f"\n━━━━━ {msg} ━━━━━"), flush=True)


def speaker(label, color, text):
    print(c(color, f"\n━━━━━ {label} ━━━━━") + f"\n{text}\n", flush=True)


def verdict(label, v, *, extra="", show_report=True):
    """One gate verdict, rendered the same way everywhere: the status line, the
    report body when it failed, and the empty-VIOLATIONS note when the checker
    stamped a verdict without findings (downgraded to a pass — surfaced so a
    checker not doing its job doesn't disappear silently)."""
    status = "PASS" if v.passed else "VIOLATIONS"
    tail = f" · {extra}" if extra else ""
    print(c("33", f"┄┄ {label}: {status}{tail} ┄┄"), flush=True)
    if show_report and not v.passed:
        print(c("2", v.report.strip()), flush=True)
    if getattr(v, "empty_violation", False):
        print(c("1;31", f"┄┄ note: {v.agent} stamped VIOLATIONS with no findings — "
                        f"treated as PASS ┄┄"), flush=True)


def show_turn(tr):
    """A play turn's gate summary (canon + conduct on one line, reports beneath)."""
    g = tr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    cv = "PASS" if g.conduct.passed else "VIOLATIONS"
    status = "CORRECTED" if tr.corrected else "clean"
    print(c("33", f"┄┄ gate: canon {nv} · conduct {cv} · {status} · "
                  f"{g.canon_sections} canon sections ┄┄"), flush=True)
    for label, v in (("CANON", g.narrative), ("CONDUCT", g.conduct)):
        if not v.passed:
            print(c("2", f"{label}:\n{v.report.strip()}"), flush=True)
        if getattr(v, "empty_violation", False):
            print(c("1;31", f"┄┄ note: {v.agent} stamped VIOLATIONS with no findings — "
                            f"treated as PASS ┄┄"), flush=True)


def show_prep(pr, *, show_report=True):
    """A PrepResult, rendered identically whether prep ran alone or after a reconcile."""
    extra = (f"{'CORRECTED' if pr.corrected else 'clean'} · "
             f"{'committed' if pr.committed else 'uncommitted'} · "
             f"{pr.gate.canon_sections} canon sections")
    verdict(f"check-plan (session {pr.n})", pr.gate.narrative, extra=extra, show_report=show_report)
    banner(f"session {pr.n} planned ({len(pr.plan)} chars)")


# ─────────────────────────────── engine ────────────────────────────────────

def with_engine(args, body, *, default_timeout=360):
    """Run `body(backend, gate)` inside the one backend lifecycle every model-calling
    command shares: boot `opencode serve`, optionally attach the live stream tap,
    guarantee shutdown, and turn BackendError / Ctrl-C into a clean exit code.

    `default_timeout` is the per model-call socket timeout when the user hasn't
    overridden it. Runtime turns are short, but a between-session stage can be one
    long dm call and needs a generous ceiling — the POST response only lands when
    the whole pass finishes, so too short a timeout kills a working call and the
    retry re-runs it."""
    timeout = args.turn_timeout or default_timeout
    note(f"starting opencode serve on :{args.port} (dir={args.dir}, call-timeout={timeout}s)")
    backend = Backend(args.dir, port=args.port, min_call_gap=args.min_gap,
                      turn_timeout=timeout, logs=LOGS)
    backend.on_retry = lambda agent, attempt, wait, reason: warn(
        f"{agent} call failed: {reason} — retry {attempt} in {wait}s")
    tap = None
    code = 0
    try:
        backend.start()
        if args.stream:
            tap = EventTap(backend.base, backend.directory).start()
            note("streaming live model output (--stream)…")
        body(backend, Gate(backend, CanonPreloader(args.dir), logs=LOGS))
        note("done.")
    except BackendError as e:
        fail(f"backend gave up: {e}")
        note("(likely still rate-limited — try `cli.py ping`)")
        code = 1
    except KeyboardInterrupt:
        print(flush=True)
        note("interrupted.")
        code = 130
    finally:
        if tap:
            tap.stop()
        note("shutting down server…")
        backend.stop()
    sys.exit(code)


def _sessions_dir(args) -> Path:
    return Path(args.dir) / "campaign" / "sessions"


def _pick_session(args, *, next_session: bool) -> int:
    """Resolve --session, defaulting from disk: prep targets the session after the
    latest plan; reconcile targets the latest *played* session (highest transcript —
    after a full wrap the newest plan is the unplayed N+1). Prints what was inferred
    so a default never runs silently against the wrong session."""
    if args.session:
        return args.session
    if next_session:
        n = (latest_session(_sessions_dir(args)) or 0) + 1
        note(f"--session not given — prepping the next session: {n}")
        return n
    played = [int(m.group(1)) for f in _sessions_dir(args).glob("session-*-transcript.md")
              if (m := re.match(r"session-(\d+)-transcript\.md$", f.name))]
    if not played:
        fail("no play transcripts on disk — nothing to reconcile (play a session first)")
        sys.exit(2)
    n = max(played)
    note(f"--session not given — reconciling the latest played session: {n}")
    return n


# ─────────────────────────────── commands ──────────────────────────────────

def cmd_play(args):
    """Drive the gated loop with the scripted `player` agent — the offline-human
    test mode. The player gets its character packet on the first turn (plus the
    story so far, on a resume) and then just plays."""
    character = ""
    if args.character and os.path.exists(args.character):
        character = re.sub(r"<!--.*?-->", "", Path(args.character).read_text(), flags=re.DOTALL).strip()
        note(f"player packet: {args.character} ({len(character)} chars)")
    elif args.character:
        warn(f"WARNING: no character packet at {args.character} — player runs blind")

    def intro(story, scene):
        parts = []
        if character:
            parts.append("[YOUR CHARACTER — read this, then stay in character for the rest "
                         f"of the session]\n\n{character}")
        if story is not None:
            parts.append(f"[This session is already underway. The story so far:]\n\n{story}")
            parts.append(f"[Continue from here — the DM's latest beat:]\n\n{scene}")
        elif parts:
            parts.append(f"[The session begins. The DM says:]\n\n{scene}")
        else:
            parts.append(scene)
        return "\n\n".join(parts)

    def body(backend, gate):
        game = Game(backend, gate, logs=LOGS)
        player_sid = backend.create_session("play-player")
        note(f"runner={game.runner_sid} player={player_sid} session={game.session}")

        scene, story = None, None
        if args.resume:
            note("resuming from transcript (silent up to the timeout if rate-limited)…")
            scene = game.resume()
            if scene is None:
                warn("nothing to resume (no transcript) — starting fresh.")
            else:
                story = game._read_transcript()
                note(f"resumed session {game.session}.")
                speaker("DM", "1;36", scene)
        if scene is None:
            note("opening the scene — first model call…")
            tr = game.start(args.kickoff)
            scene = tr.final
            speaker("DM", "1;36", scene)
            show_turn(tr)

        for i in range(1, args.turns + 1):
            msg = intro(story, scene) if i == 1 else scene
            story = None  # only the first turn carries the story
            note(f"turn {i}: waiting on the player…")
            player = backend.prompt(player_sid, "player", msg)
            speaker(f"PLAYER · turn {i}", "1;32", player)

            note(f"turn {i}: waiting on the DM (draft + gate)…")
            tr = game.turn(player)
            scene = tr.final
            speaker("DM", "1;36", scene)
            show_turn(tr)

    with_engine(args, body)


def cmd_prep(args):
    def body(backend, gate):
        n = _pick_session(args, next_session=True)
        note(f"prepping session {n} — the dm authors, then the gate runs…")
        pr = Planner(backend, gate, logs=LOGS).prep_session(n, commit=args.commit)
        print(flush=True)
        show_prep(pr, show_report=not args.stream)

    with_engine(args, body, default_timeout=1800)


def cmd_reconcile(args):
    def body(backend, gate):
        n = _pick_session(args, next_session=False)
        note(f"reconciling session {n} — staged apply, gated stage by stage…")
        rr = Reconciler(backend, gate, logs=LOGS).reconcile_session(
            n, commit=args.commit, prep=not args.no_prep, fresh=args.fresh)

        print(flush=True)
        for label, g in (("check-digest", rr.digest), ("check-feedback", rr.feedback),
                         ("check-propagation", rr.propagation)):
            if g is not None:  # None = stage skipped this run (resumed past it)
                verdict(label, g.narrative, show_report=not args.stream)
        if rr.lint_incomplete:
            print(c("33", f"┄┄ completeness lint: {rr.lint_incomplete} file(s) flagged · "
                          f"correction dispatched ┄┄"), flush=True)
        banner(f"session {rr.n} reconciled{' · committed' if rr.committed else ''}")
        if rr.prep is not None:
            show_prep(rr.prep, show_report=not args.stream)

    with_engine(args, body, default_timeout=1800)


def cmd_status(args):
    """Where the campaign stands — a renderer over `campaign_status()` (disk only,
    no server, no model). The TUI's status modal renders the same snapshot."""
    root = Path(args.dir)
    if not (root / "campaign").is_dir():
        print(f"campaign: {root}\nphase: no campaign yet — the TUI opens in setup "
              f"(`cli.py tui --live`)")
        return
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
    print(c("31", line + " — run `cli.py lint` for detail") if st.incomplete else c("32", line))

    if st.git_state is not None:
        state = "dirty (uncommitted campaign changes)" if st.git_state == "dirty" else "clean"
        print(f"git: {state}" + (f' · last: "{st.last_commit}"' if st.last_commit else ""))


def cmd_lint(args):
    """Deterministic entity-completeness lint — no backend, no model calls."""
    from orchestrator.completeness import lint_dir
    reports = lint_dir(args.dir)
    incomplete = [r for r in reports if not r.ok]
    for r in reports:
        rel = r.path.relative_to(args.dir) if r.path.is_absolute() else r.path
        if r.ok:
            print(c("32", f"  ✓ {rel}"))
        else:
            detail = []
            if r.missing:
                detail.append("missing: " + ", ".join(r.missing))
            if r.missing_sections:
                detail.append("sections: " + ", ".join(r.missing_sections))
            print(c("31", f"  ✗ {rel}  [{r.type}]  " + "  ·  ".join(detail)))
    n, bad = len(reports), len(incomplete)
    print(c("1;36", f"\n━━ {n - bad}/{n} entity files complete ━━"))
    sys.exit(1 if incomplete else 0)


def cmd_tui(args):
    """Hand off to the Textual app (needs the venv's textual)."""
    venv_py = OPENCODE / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    cmd = [py, "-m", "tui"]
    if args.live:
        cmd.append("--live")
    if args.setup:
        cmd.append("--setup")
    if args.theme:
        cmd += ["--theme", args.theme]
    sys.exit(subprocess.call(cmd, cwd=str(OPENCODE)))


def cmd_ping(args):
    sys.exit(subprocess.call([str(DEV / "ping.sh"), str(args.count)]))


# ─────────────────────────────── parser ────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(prog="gm-llm", description="orchestrator control CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # shared flags for every model-calling command
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=str(ROOT))
    common.add_argument("--port", type=int, default=4181)
    common.add_argument("--min-gap", type=float, default=1.0,
                        help="min seconds between any two model calls")
    common.add_argument("--stream", action="store_true",
                        help="stream the dm/checker output live as it generates (verbose)")
    common.add_argument("--turn-timeout", type=int, default=0,
                        help="per model-call timeout in seconds (0 = per-command default; "
                             "play=360, prep/reconcile=1800)")

    p = sub.add_parser("status", help="where the campaign stands (disk only, no model)")
    p.add_argument("--dir", default=str(ROOT))
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("play", parents=[common],
                       help="drive the gated loop with the scripted player")
    p.add_argument("--turns", type=int, default=6)
    p.add_argument("--resume", action="store_true",
                   help="continue the latest session from its transcript")
    p.add_argument("--kickoff", default="Let's begin the session.")
    p.add_argument("--character", default=str(DEV / "dallid.player.md"),
                   help="player packet injected into the player's first message ('' to skip)")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("prep", parents=[common], help="PRE: author + gate + commit the session plan")
    p.add_argument("--session", type=int, default=0, help="session to prep (default: next)")
    p.add_argument("--no-commit", dest="commit", action="store_false",
                   help="dry run — skip the git commit")
    p.set_defaults(func=cmd_prep)

    p = sub.add_parser("reconcile", parents=[common], help="POST: the staged post-session pipeline")
    p.add_argument("--session", type=int, default=0, help="session to reconcile (default: latest)")
    p.add_argument("--no-commit", dest="commit", action="store_false",
                   help="dry run — skip the git commits")
    p.add_argument("--no-prep", action="store_true", help="skip prepping session N+1")
    p.add_argument("--fresh", action="store_true",
                   help="clear stage markers and re-run from scratch")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("tui", help="launch the Textual app (mock by default)")
    p.add_argument("--live", action="store_true")
    p.add_argument("--setup", action="store_true",
                   help="mock only: start in the new-campaign setup phase")
    p.add_argument("--theme", default=None)
    p.set_defaults(func=cmd_tui)

    p = sub.add_parser("lint", help="check entity files against the completeness contract")
    p.add_argument("--dir", default=str(ROOT))
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("ping", help="probe the model's rate-limit state")
    p.add_argument("count", nargs="?", type=int, default=1, help="number of back-to-back probes")
    p.set_defaults(func=cmd_ping)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
