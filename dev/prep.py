#!/usr/bin/env python3
"""
Prep — headless validation of orchestrated PRE-session planning (O5).

Boots a real opencode backend and runs the `Planner`: the dm authors the session
plan, the orchestrator gates it in code with `check-plan`, applies one bounded
correction, and (optionally) commits. The same determinism as the per-turn loop,
one stage earlier — the dm never decides *whether* to check.

    python3 .opencode/dev/prep.py --session 2            # prep, don't commit
    python3 .opencode/dev/prep.py --session 2 --commit   # prep and commit the plan

This is a dev rig, not the engine. Ctrl-C stops it and shuts the server down.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # put .opencode on the path
from orchestrator import Backend, BackendError, CanonPreloader, Gate, Planner  # noqa: E402

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

_COLOR = sys.stdout.isatty()
def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def show_prep(pr):
    g = pr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    status = "CORRECTED" if pr.corrected else "clean"
    commit = "committed" if pr.committed else "uncommitted"
    print(c("33", f"\n┄┄ check-plan: {nv} · {status} · {commit} · "
                  f"{g.canon_sections} canon sections ┄┄"), flush=True)
    if not g.narrative.passed:
        print(c("2", g.narrative.report.strip()), flush=True)
    print(c("1;36", f"\n━━━━━ session {pr.n} plan ({len(pr.plan)} chars) ━━━━━"), flush=True)
    print(c("2", "(behind the screen — full of spoilers; not shown to the player)"), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=int, required=True, help="session number N to prep")
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--dir", default=PROJECT_ROOT)
    ap.add_argument("--commit", action="store_true", help="commit the plan (campaign: session N plan)")
    ap.add_argument("--min-gap", type=float, default=1.0, help="min seconds between any two model calls")
    args = ap.parse_args()
    directory = str(Path(args.dir).resolve())

    def on_retry(agent, attempt, wait, reason):
        print(c("33", f"[harness] {agent} call failed: {reason} — retry {attempt} in {wait}s"), flush=True)

    print(f"[harness] starting opencode serve on :{args.port} (dir={directory})", flush=True)
    backend = Backend(directory, port=args.port, min_call_gap=args.min_gap)
    backend.on_retry = on_retry
    try:
        backend.start()
        gate = Gate(backend, CanonPreloader(directory))
        planner = Planner(backend, gate, checks_log="/tmp/orchestrator-checks.log")
        print(f"[harness] dm session={planner.dm_sid}", flush=True)

        print(c("2", f"[harness] prepping session {args.session} — the dm authors, then the gate runs "
                     f"(silent up to the timeout if rate-limited)…"), flush=True)
        pr = planner.prep_session(args.session, commit=args.commit)
        show_prep(pr)
        print("\n[harness] done.", flush=True)
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
