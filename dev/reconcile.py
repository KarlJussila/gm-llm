#!/usr/bin/env python3
"""
Reconcile — headless validation of orchestrated POST-session reconcile (O6).

Boots a real opencode backend and runs the `Reconciler`: the dm applies a played
session into canon and state (digest, deltas, new canon, arc bodies, ledger, state
snapshots, feedback), then the orchestrator gates the result in code with
`check-propagation`, applies one bounded correction, and (optionally) commits. The
dm never decides *whether* to verify — the orchestrator does, every time.

    python3 .opencode/dev/reconcile.py --session 1            # reconcile, don't commit
    python3 .opencode/dev/reconcile.py --session 1 --commit   # reconcile and commit
    python3 .opencode/dev/reconcile.py --session 1 --prep     # then prep session N+1

This is a dev rig, not the engine. Ctrl-C stops it and shuts the server down.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # put .opencode on the path
from orchestrator import (  # noqa: E402
    Backend, BackendError, CanonPreloader, Gate, Planner, Reconciler,
)

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

_COLOR = sys.stdout.isatty()
def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def show_reconcile(rr):
    g = rr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    status = "CORRECTED" if rr.corrected else "clean"
    commit = "committed" if rr.committed else "uncommitted"
    print(c("33", f"\n┄┄ check-propagation: {nv} · {status} · {commit} ┄┄"), flush=True)
    if not g.narrative.passed:
        print(c("2", g.narrative.report.strip()), flush=True)
    print(c("1;36", f"\n━━━━━ session {rr.n} reconciled ━━━━━"), flush=True)


def show_prep(pr):
    g = pr.gate
    nv = "PASS" if g.narrative.passed else "VIOLATIONS"
    status = "CORRECTED" if pr.corrected else "clean"
    commit = "committed" if pr.committed else "uncommitted"
    print(c("33", f"\n┄┄ check-plan (session {pr.n}): {nv} · {status} · {commit} · "
                  f"{g.canon_sections} canon sections ┄┄"), flush=True)
    if not g.narrative.passed:
        print(c("2", g.narrative.report.strip()), flush=True)
    print(c("1;36", f"\n━━━━━ session {pr.n} planned ({len(pr.plan)} chars) ━━━━━"), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=int, required=True, help="session number N to reconcile")
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--dir", default=PROJECT_ROOT)
    ap.add_argument("--commit", action="store_true", help="commit (campaign: post-session N updates)")
    ap.add_argument("--prep", action="store_true", help="after reconcile, prep session N+1")
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
        reconciler = Reconciler(backend, gate, checks_log="/tmp/orchestrator-checks.log")
        print(f"[harness] dm session={reconciler.dm_sid}", flush=True)

        print(c("2", f"[harness] reconciling session {args.session} — the dm applies, then the gate "
                     f"runs (silent up to the timeout if rate-limited)…"), flush=True)
        rr = reconciler.reconcile_session(args.session, commit=args.commit)
        show_reconcile(rr)

        if args.prep:
            n2 = args.session + 1
            planner = Planner(backend, gate, checks_log="/tmp/orchestrator-checks.log")
            print(c("2", f"\n[harness] prepping session {n2}…"), flush=True)
            pr = planner.prep_session(n2, commit=args.commit)
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
