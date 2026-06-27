#!/usr/bin/env python3
"""
Autoplay — headless validation of the orchestrator core.

Boots a real opencode backend, builds the orchestrator `Game` (which owns the
deterministic gate), and drives it with the scripted `player` agent — so we can
watch the loop run end-to-end without a human: the runner drafts, the gate runs
EVERY turn, one bounded correction, paced calls. The check verdicts print inline.

    python3 .opencode/dev/autoplay.py --turns 12

This is a dev rig, not the engine. Ctrl-C stops it and shuts the server down.
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # put .opencode on the path
from orchestrator import Backend, BackendError, CanonPreloader, Gate, Game  # noqa: E402

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

_COLOR = sys.stdout.isatty()
def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def show_dm(text):
    print(c("1;36", "\n━━━━━ DM ━━━━━") + f"\n{text}\n", flush=True)


def show_player(i, text):
    print(c("1;32", f"\n━━━━━ PLAYER · turn {i} ━━━━━") + f"\n{text}\n", flush=True)


def show_gate(tr):
    g = tr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    cv = "PASS" if g.conduct.passed else "VIOLATIONS"
    status = "CORRECTED" if tr.corrected else "clean"
    print(c("33", f"┄┄ gate: canon {nv} · conduct {cv} · {status} · {g.canon_sections} canon sections ┄┄"), flush=True)
    if not g.narrative.passed:
        print(c("2", "CANON:\n" + g.narrative.report.strip()), flush=True)
    if not g.conduct.passed:
        print(c("2", "CONDUCT:\n" + g.conduct.report.strip()), flush=True)
    if tr.corrected or not g.narrative.passed or not g.conduct.passed:
        print("", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--dir", default=PROJECT_ROOT)
    ap.add_argument("--kickoff", default="Let's begin the session.")
    ap.add_argument("--min-gap", type=float, default=1.0, help="min seconds between any two model calls")
    ap.add_argument("--character", default=str(Path(__file__).resolve().parent / "dallid.player.md"),
                    help="player packet injected into the player's first message ('' to skip)")
    args = ap.parse_args()
    directory = str(Path(args.dir).resolve())

    character = ""
    if args.character and os.path.exists(args.character):
        character = re.sub(r"<!--.*?-->", "", Path(args.character).read_text(), flags=re.DOTALL).strip()
        print(f"[harness] player packet: {args.character} ({len(character)} chars)", flush=True)
    elif args.character:
        print(f"[harness] WARNING: no character packet at {args.character} — player runs blind", flush=True)

    def on_retry(agent, attempt, wait, reason):
        print(c("33", f"[harness] {agent} call failed: {reason} — retry {attempt} in {wait}s"), flush=True)

    print(f"[harness] starting opencode serve on :{args.port} (dir={directory})", flush=True)
    backend = Backend(directory, port=args.port, min_call_gap=args.min_gap)
    backend.on_retry = on_retry
    try:
        backend.start()
        gate = Gate(backend, CanonPreloader(directory))
        game = Game(backend, gate, checks_log="/tmp/orchestrator-checks.log")
        player_sid = backend.create_session("autoplay-player")
        print(f"[harness] runner={game.runner_sid} player={player_sid}", flush=True)

        def waiting(msg):
            print(c("2", f"[harness] {msg}"), flush=True)

        waiting("opening the scene — first model call (silent up to the timeout if rate-limited)…")
        tr = game.start(args.kickoff)
        show_dm(tr.final)
        show_gate(tr)

        for i in range(1, args.turns + 1):
            msg = tr.final
            if i == 1 and character:
                msg = (f"[YOUR CHARACTER — read this, then stay in character for the rest of the session]\n\n"
                       f"{character}\n\n[The session begins. The DM says:]\n\n{tr.final}")
            waiting(f"turn {i}: waiting on the player…")
            player = backend.prompt(player_sid, "player", msg)
            show_player(i, player)

            waiting(f"turn {i}: waiting on the DM (draft + gate)…")
            tr = game.turn(player)
            show_dm(tr.final)
            show_gate(tr)

        print("[harness] done.", flush=True)
    except BackendError as e:
        print(c("1;31", f"[harness] backend gave up: {e}"), flush=True)
        print("[harness] (likely still rate-limited — try again later)", flush=True)
    except KeyboardInterrupt:
        print("\n[harness] interrupted.", flush=True)
    finally:
        print("[harness] shutting down server…", flush=True)
        backend.stop()


if __name__ == "__main__":
    main()
