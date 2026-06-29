#!/usr/bin/env python3
"""
campaign — orchestrator control CLI.

One entry point for every mode, so driving the engine (and, soon, sweeping it for
the benchmark) is uniform. Each subcommand is a thin front-end over the orchestrator
core (`Game`, `Planner`, `Reconciler`); the determinism lives in the library, not here.

    python .opencode/dev/cli.py play      --turns 6 [--resume]
    python .opencode/dev/cli.py prep      --session 3 [--commit]
    python .opencode/dev/cli.py reconcile --session 2 [--commit] [--prep]
    python .opencode/dev/cli.py tui       [--live] [--theme tokyo-night]
    python .opencode/dev/cli.py ping      [N]
    python .opencode/dev/cli.py bench      ...        # stub — wired in O4

`play` boots a real backend and drives the gated loop with the scripted `player`
agent (the auto-mode); `--resume` continues the latest session from its transcript
instead of opening a fresh scene. Ctrl-C stops any mode and shuts the server down.
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
    Backend, BackendError, CanonPreloader, Gate, Game, Planner, Reconciler,
)
from orchestrator.stream import EventTap  # noqa: E402

_COLOR = sys.stdout.isatty()
def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


# ───────────────────────── shared backend plumbing ─────────────────────────

def _backend(args, default_timeout: int = 360):
    """`default_timeout` is the per model-call socket timeout when the user hasn't
    overridden it. Runtime turns are short, but a between-session apply pass is one
    long `dm` call (log-extractor + every write) and needs a generous ceiling — the
    POST response only lands when the whole pass finishes, so too short a timeout
    kills a working call and the retry re-runs it."""
    timeout = args.turn_timeout or default_timeout
    def on_retry(agent, attempt, wait, reason):
        print(c("33", f"[harness] {agent} call failed: {reason} — retry {attempt} in {wait}s"), flush=True)
    print(f"[harness] starting opencode serve on :{args.port} (dir={args.dir}, call-timeout={timeout}s)", flush=True)
    b = Backend(args.dir, port=args.port, min_call_gap=args.min_gap, turn_timeout=timeout)
    b.on_retry = on_retry
    return b

CHECKS_LOG = "/tmp/orchestrator-checks.log"


# ──────────────────────────────── play ─────────────────────────────────────

def _show_dm(text):
    print(c("1;36", "\n━━━━━ DM ━━━━━") + f"\n{text}\n", flush=True)

def _show_player(i, text):
    print(c("1;32", f"\n━━━━━ PLAYER · turn {i} ━━━━━") + f"\n{text}\n", flush=True)

def _empty_note(*verdicts):
    """Surface a checker that stamped VIOLATIONS with no findings (downgraded to a
    pass) — so a checker not doing its job doesn't disappear silently."""
    for v in verdicts:
        if getattr(v, "empty_violation", False):
            print(c("1;31", f"┄┄ note: {v.agent} stamped VIOLATIONS with no findings — "
                            f"treated as PASS (checker output was just the verdict line) ┄┄"), flush=True)


def _show_gate(tr):
    g = tr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    cv = "PASS" if g.conduct.passed else "VIOLATIONS"
    status = "CORRECTED" if tr.corrected else "clean"
    print(c("33", f"┄┄ gate: canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon sections ┄┄"), flush=True)
    if not g.narrative.passed:
        print(c("2", "CANON:\n" + g.narrative.report.strip()), flush=True)
    if not g.conduct.passed:
        print(c("2", "CONDUCT:\n" + g.conduct.report.strip()), flush=True)
    _empty_note(g.narrative, g.conduct)


def _player_intro(character, story, scene):
    """The player agent's first message: its character packet, plus either the
    opening scene (fresh) or the story so far and where to pick up (resume)."""
    if story is not None:
        head = (f"[YOUR CHARACTER — read this, then stay in character]\n\n{character}\n\n"
                f"[This session is already underway. The story so far:]\n\n{story}\n\n"
                f"[Continue from here — the DM's latest beat:]\n\n{scene}") if character else (
                f"[This session is already underway. The story so far:]\n\n{story}\n\n"
                f"[Continue from here — the DM's latest beat:]\n\n{scene}")
        return head
    if character:
        return (f"[YOUR CHARACTER — read this, then stay in character for the rest of the session]\n\n"
                f"{character}\n\n[The session begins. The DM says:]\n\n{scene}")
    return scene


def cmd_play(args):
    character = ""
    if args.character and os.path.exists(args.character):
        character = re.sub(r"<!--.*?-->", "", Path(args.character).read_text(), flags=re.DOTALL).strip()
        print(f"[harness] player packet: {args.character} ({len(character)} chars)", flush=True)
    elif args.character:
        print(f"[harness] WARNING: no character packet at {args.character} — player runs blind", flush=True)

    backend = _backend(args)
    tap = None
    try:
        backend.start()
        tap = EventTap(backend.base, backend.directory).start() if args.stream else None
        if tap:
            print(c("2", "[harness] streaming live model output (--stream)…"), flush=True)
        game = Game(backend, Gate(backend, CanonPreloader(args.dir)), checks_log=CHECKS_LOG)
        player_sid = backend.create_session("play-player")
        print(f"[harness] runner={game.runner_sid} player={player_sid} session={game.session}", flush=True)

        scene, story = None, None
        if args.resume:
            print(c("2", "[harness] resuming from transcript (silent up to the timeout if rate-limited)…"), flush=True)
            scene = game.resume()
            if scene is None:
                print(c("33", "[harness] nothing to resume (no transcript) — starting fresh."), flush=True)
            else:
                story = game._read_transcript()
                print(c("2", f"[harness] resumed session {game.session}."), flush=True)
                _show_dm(scene)

        if scene is None:
            print(c("2", "[harness] opening the scene — first model call…"), flush=True)
            tr = game.start(args.kickoff)
            scene = tr.final
            _show_dm(scene); _show_gate(tr)

        for i in range(1, args.turns + 1):
            msg = _player_intro(character, story, scene) if i == 1 else scene
            story = None  # only the first resumed turn needs the story
            print(c("2", f"[harness] turn {i}: waiting on the player…"), flush=True)
            player = backend.prompt(player_sid, "player", msg)
            _show_player(i, player)

            print(c("2", f"[harness] turn {i}: waiting on the DM (draft + gate)…"), flush=True)
            tr = game.turn(player)
            scene = tr.final
            _show_dm(scene); _show_gate(tr)

        print("[harness] done.", flush=True)
    except BackendError as e:
        print(c("1;31", f"[harness] backend gave up: {e}"), flush=True)
        print("[harness] (likely still rate-limited — try `cli.py ping`)", flush=True)
    except KeyboardInterrupt:
        print("\n[harness] interrupted.", flush=True)
    finally:
        if tap:
            tap.stop()
        print("[harness] shutting down server…", flush=True)
        backend.stop()


# ──────────────────────────────── prep ─────────────────────────────────────

def cmd_prep(args):
    backend = _backend(args, default_timeout=1800)
    tap = None
    try:
        backend.start()
        tap = EventTap(backend.base, backend.directory).start() if args.stream else None
        gate = Gate(backend, CanonPreloader(args.dir))
        planner = Planner(backend, gate, checks_log=CHECKS_LOG)
        print(c("2", f"[harness] prepping session {args.session} — the dm authors, then the gate runs…"), flush=True)
        pr = planner.prep_session(args.session, commit=args.commit)
        nv = "PASS" if pr.gate.narrative.passed else "VIOLATIONS"
        print(c("33", f"\n┄┄ check-plan: {nv} · {'CORRECTED' if pr.corrected else 'clean'} · "
                      f"{'committed' if pr.committed else 'uncommitted'} · {pr.gate.canon_sections} canon sections ┄┄"), flush=True)
        if not args.stream and not pr.gate.narrative.passed:
            print(c("2", pr.gate.narrative.report.strip()), flush=True)
        _empty_note(pr.gate.narrative)
        print(c("1;36", f"\n━━━━━ session {pr.n} planned ({len(pr.plan)} chars) ━━━━━"), flush=True)
        print("[harness] done.", flush=True)
    except BackendError as e:
        print(c("1;31", f"[harness] backend gave up: {e}"), flush=True)
    except KeyboardInterrupt:
        print("\n[harness] interrupted.", flush=True)
    finally:
        if tap:
            tap.stop()
        backend.stop()


# ─────────────────────────────── reconcile ─────────────────────────────────

def cmd_reconcile(args):
    backend = _backend(args, default_timeout=1800)
    tap = None
    try:
        backend.start()
        tap = EventTap(backend.base, backend.directory).start() if args.stream else None
        gate = Gate(backend, CanonPreloader(args.dir))
        reconciler = Reconciler(backend, gate, checks_log=CHECKS_LOG)
        print(c("2", f"[harness] reconciling session {args.session} — the dm applies, then the gate runs…"), flush=True)
        rr = reconciler.reconcile_session(args.session, commit=args.commit)
        nv = "PASS" if rr.gate.narrative.passed else "VIOLATIONS"
        print(c("33", f"\n┄┄ check-propagation: {nv} · {'CORRECTED' if rr.corrected else 'clean'} · "
                      f"{'committed' if rr.committed else 'uncommitted'} ┄┄"), flush=True)
        if not args.stream and not rr.gate.narrative.passed:
            print(c("2", rr.gate.narrative.report.strip()), flush=True)
        _empty_note(rr.gate.narrative)
        print(c("1;36", f"\n━━━━━ session {rr.n} reconciled ━━━━━"), flush=True)

        if args.prep:
            n2 = args.session + 1
            print(c("2", f"\n[harness] prepping session {n2}…"), flush=True)
            pr = Planner(backend, gate, checks_log=CHECKS_LOG).prep_session(n2, commit=args.commit)
            nv = "PASS" if pr.gate.narrative.passed else "VIOLATIONS"
            print(c("33", f"┄┄ check-plan (session {pr.n}): {nv} · {'CORRECTED' if pr.corrected else 'clean'} · "
                          f"{'committed' if pr.committed else 'uncommitted'} ┄┄"), flush=True)
            _empty_note(pr.gate.narrative)
            print(c("1;36", f"━━━━━ session {pr.n} planned ━━━━━"), flush=True)
        print("[harness] done.", flush=True)
    except BackendError as e:
        print(c("1;31", f"[harness] backend gave up: {e}"), flush=True)
    except KeyboardInterrupt:
        print("\n[harness] interrupted.", flush=True)
    finally:
        if tap:
            tap.stop()
        backend.stop()


# ─────────────────────────── tui / ping / bench ────────────────────────────

def cmd_tui(args):
    """Hand off to the Textual app (needs the venv's textual)."""
    venv_py = OPENCODE / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    cmd = [py, "-m", "tui"]
    if args.live:
        cmd.append("--live")
    if args.theme:
        cmd += ["--theme", args.theme]
    sys.exit(subprocess.call(cmd, cwd=str(OPENCODE)))


def cmd_ping(args):
    sys.exit(subprocess.call([str(DEV / "ping.sh"), str(args.count)]))


def cmd_bench(args):
    print(c("1;33", "bench is not wired yet (O4). Planned: swap the human player for a scripted/"
                    "model player, score from gate verdicts, sweep models via opencode providers."))
    sys.exit(2)


# ──────────────────────────────── parser ───────────────────────────────────

def main():
    ap = argparse.ArgumentParser(prog="campaign", description="orchestrator control CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # shared backend args
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", default=str(ROOT))
    common.add_argument("--port", type=int, default=4181)
    common.add_argument("--min-gap", type=float, default=1.0, help="min seconds between any two model calls")
    common.add_argument("--stream", action="store_true",
                        help="stream the dm/checker output live as it generates (verbose)")
    common.add_argument("--turn-timeout", type=int, default=0,
                        help="per model-call timeout in seconds (0 = per-command default; "
                             "play=360, prep/reconcile=1800). Raise for very long apply passes.")

    p = sub.add_parser("play", parents=[common], help="drive the gated loop with the scripted player")
    p.add_argument("--turns", type=int, default=6)
    p.add_argument("--resume", action="store_true", help="continue the latest session from its transcript")
    p.add_argument("--kickoff", default="Let's begin the session.")
    p.add_argument("--character", default=str(DEV / "dallid.player.md"),
                   help="player packet injected into the player's first message ('' to skip)")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("prep", parents=[common], help="orchestrate PRE-session planning")
    p.add_argument("--session", type=int, required=True)
    p.add_argument("--commit", action="store_true")
    p.set_defaults(func=cmd_prep)

    p = sub.add_parser("reconcile", parents=[common], help="orchestrate POST-session reconcile")
    p.add_argument("--session", type=int, required=True)
    p.add_argument("--commit", action="store_true")
    p.add_argument("--prep", action="store_true", help="after reconcile, prep session N+1")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("tui", help="launch the Textual app (mock by default)")
    p.add_argument("--live", action="store_true")
    p.add_argument("--theme", default=None)
    p.set_defaults(func=cmd_tui)

    p = sub.add_parser("ping", help="probe the model's rate-limit state")
    p.add_argument("count", nargs="?", type=int, default=1, help="number of back-to-back probes")
    p.set_defaults(func=cmd_ping)

    p = sub.add_parser("bench", help="model-vs-model benchmark (not yet wired)")
    p.set_defaults(func=cmd_bench)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
