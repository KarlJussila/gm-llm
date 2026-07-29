#!/usr/bin/env python3
"""Standalone check for a bench batch watched in the TUI — no pytest; run me directly.

Drives the real `PlayApp` headlessly (Textual's `run_test` pilot) over a real
`bench.runner.run_batch`, with only the expensive seams faked (the fakes are
`dev/test_bench.py`'s, imported rather than re-spelled). So this is the app's actual event
loop, workers and threads, the actual batch, and the actual archives — frontends step 4.

What it pins:

  - **The frontend is inert.** A watched batch and a headless one produce the same outcomes,
    the same turn counts and the same archive event streams — including when someone types
    into the watching app, which must reach nothing. This is the comparability invariant
    (design/frontends.md § Constraints), which until now had nothing enforcing it.
  - **The chrome exists.** The batch header tracks run *k* of *N* and tallies the outcomes,
    and each run's play renders into the scene through the lifecycle the app attaches per
    run — the thing `PlayApp` could not do while it assumed one campaign dir for life.
  - **Quitting stops the batch honestly.** The run in flight ends `incomplete` and
    *resumable* — no `cap` event, which would archive a ceiling it never hit — the batch
    opens no further runs, and the thread unwinds far enough to write the manifest line.
"""

import asyncio
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))       # so `gm_llm` imports straight from the checkout
sys.path.insert(0, str(REPO / "dev"))  # …and the bench fakes next door

import test_bench as tb  # noqa: E402

from gm_llm.bench import runner  # noqa: E402
from gm_llm.tui.app import PlayApp  # noqa: E402
from gm_llm.tui.widgets import BatchHeader, DMBlock, PlayerLine  # noqa: E402


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


async def until(pilot, cond, what, timeout=30.0):
    """Wait for a condition instead of for a clock — the batch runs on its own thread, so
    the only thing a test may rely on is the order of what it observes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            await pilot.pause()
            print(f"  ok: {what}")
            return
        await pilot.pause()
        await asyncio.sleep(0.01)
    print(f"FAIL: timed out waiting for {what}")
    sys.exit(1)


def events(out_dir, record):
    """The event-name stream of a run's archive — the shape a grader reads, with the
    volatile parts (timestamps, ids, narration) left out of the comparison."""
    path = Path(out_dir) / record["archive"]
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            out.append((e.get("event"), bool(e.get("session_complete"))))
    return out


def header_text(app):
    return app.query_one(BatchHeader).line


class _PacedBackend(tb.FakeBackend):
    """`test_bench`'s play backend, slowed down so a run can be observed and interfered with
    while it is still playing: `delay` per runner call, and `gate` parks the run's `gate_at`-th
    draft until the test releases it. Nothing here is play behaviour — the fakes are instant,
    and a batch that finishes between two pilot pauses can't be watched or quit."""

    def __init__(self, directory, *, complete_after=None, delay=0.0, gate=None, gate_at=2):
        super().__init__(directory, complete_after=complete_after)
        self._delay, self._gate, self._gate_at = delay, gate, gate_at

    def prompt_full(self, sid, agent, message, whole=False):
        if not whole:
            if self._delay:
                time.sleep(self._delay)
            if self._gate is not None and self._runner_calls + 1 == self._gate_at:
                self._gate.wait(20)
        return super().prompt_full(sid, agent, message, whole=whole)


def _fakes(*, complete_after=None, delay=0.0, gate=None, reconciled=None):
    """A run_batch bundle over the paced backend: no init, no npm, no opencode, and the
    lifecycle's one expensive seam (the between-session pass) recorded instead of run."""
    runs = {"n": 0}

    def backend_factory(directory, **kw):
        runs["n"] += 1
        return _PacedBackend(directory, complete_after=complete_after, delay=delay,
                             gate=gate if runs["n"] == 1 else None)

    return dict(init=lambda d: None, install=lambda d: (True, "noop"),
                backend_factory=backend_factory,
                gate_factory=lambda backend, directory, logs: tb.FakeGate(),
                lifecycle_factory=tb._lifecycle_factory(
                    None if reconciled is None else reconciled.append),
                note=lambda m: None)


# ── scenarios ─────────────────────────────────────────────────────────────────

async def watching_a_batch_changes_nothing_about_it():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fixture = tb._make_fixture(tmp / "fixture")
        headless_out, watched_out = tmp / "headless", tmp / "watched"
        for out in (headless_out, watched_out):
            tb._make_template(out / "template")  # pre-seeded: no init, no npm

        headless = runner.run_batch(fixture, headless_out, runs=2, turn_cap=10,
                                    **_fakes(complete_after=2))
        check(len(headless) == 2 and all(r["outcome"] == "complete" for r in headless),
              "the headless batch played two runs to a natural close")

        gate, watched = threading.Event(), []

        def drive(hooks):
            watched.extend(runner.run_batch(
                fixture, watched_out, runs=2, turn_cap=10, hooks=hooks,
                **{**_fakes(complete_after=2, gate=gate), "note": app.note}))

        app = PlayApp(batch=drive)
        async with app.run_test() as pilot:
            # Run 1 is parked on its first turn's draft, so what follows is deterministic.
            await until(pilot, lambda: app.lc is not None, "run 1 attaches its lifecycle")
            check("run 1/2" in header_text(app), f"the header says which run — {header_text(app)}")

            # Read-only: typing at a watched batch must reach nothing. If it did, the
            # archive comparison below would diverge.
            inp = app.query_one("#cmd")
            inp.focus()
            inp.value = "I try to play someone else's benchmark run."
            await pilot.press("enter")
            gate.set()

            await until(pilot, lambda: len(watched) == 2, "both runs play and record")
            await until(pilot, lambda: app.lc is None, "the last run detaches on close")

            check(len(app.query(DMBlock)) == 6,
                  f"every run's opening + 2 turns render — {len(app.query(DMBlock))} beats")
            check(len(app.query(PlayerLine)) == 4,
                  f"the agent player's lines are echoed — {len(app.query(PlayerLine))}")
            check("2 complete" in header_text(app),
                  f"the header tallies the finished runs — {header_text(app)}")
            app.exit()
        app.join_batch(timeout=30)

        check([r["outcome"] for r in watched] == [r["outcome"] for r in headless],
              f"same outcomes as headless — {[r['outcome'] for r in watched]}")
        check([r["turns"] for r in watched] == [r["turns"] for r in headless],
              f"same turn counts as headless — {[r['turns'] for r in watched]}")
        for i, (w, h) in enumerate(zip(watched, headless)):
            check(events(watched_out, w) == events(headless_out, h),
                  f"run {i + 1}'s archive stream is identical to the headless one")
    print("watching_a_batch_changes_nothing_about_it: the frontend is inert.\n")


async def quitting_stops_the_batch_and_leaves_the_run_resumable():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fixture = tb._make_fixture(tmp / "fixture")
        out = tmp / "out"
        tb._make_template(out / "template")

        reconciled, records = [], []
        # complete_after=None: the run never wraps, so it is still playing when we quit.
        fakes = _fakes(delay=0.05, reconciled=reconciled)

        def drive(hooks):
            records.extend(runner.run_batch(fixture, out, runs=2, turn_cap=50, hooks=hooks,
                                            **{**fakes, "note": app.note}))

        app = PlayApp(batch=drive)
        async with app.run_test() as pilot:
            await until(pilot, lambda: len(app.query(DMBlock)) >= 3,
                        "run 1 is playing (opening + two turns)")
            app.exit()
        app.join_batch(timeout=30)

        check(len(records) == 1, f"the batch stopped instead of opening run 2 — {len(records)}")
        rec = records[0]
        check(rec["outcome"].startswith("incomplete") and "stopped" in rec["outcome"],
              f"the run in flight is incomplete, not failed — {rec['outcome']}")
        check(rec["turns"] >= 1, f"the turns it played are its resume point — {rec['turns']}")
        check(reconciled == [], "an unwrapped session is not reconciled")

        archive = Path(out) / rec["archive"]
        raw = [json.loads(l) for l in archive.read_text(encoding="utf-8").splitlines() if l.strip()]
        check(not any(e["event"] == "cap" for e in raw),
              "quitting is not a cap breach — no ceiling the run never hit")
        state, turns = runner.classify_archive(archive)
        check(state == "resumable", f"`bench run --resume` can pick it back up — {state}")

        manifest = [json.loads(l) for l in
                    (out / "batch.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        check(len(manifest) == 1 and manifest[0]["outcome"] == rec["outcome"],
              f"the manifest line was written on the way out — {manifest}")
    print("quitting_stops_the_batch_and_leaves_the_run_resumable: an exit is not an ending.\n")


if __name__ == "__main__":
    asyncio.run(watching_a_batch_changes_nothing_about_it())
    asyncio.run(quitting_stops_the_batch_and_leaves_the_run_resumable())
    print("OK — bench in the TUI: batch chrome, per-run lifecycles, an inert frontend.")
