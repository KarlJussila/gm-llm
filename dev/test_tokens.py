#!/usr/bin/env python3
"""Standalone checks for `gm-llm tokens` — no pytest; run me directly.

Builds a throwaway SQLite store shaped like opencode's `session` table and reads it back,
so the whole module is exercised with no opencode, no network, and no dependence on the
developer's real store. The point of most of these is the *failure* behaviour: this module
reads someone else's schema, so a missing store or a renamed column must degrade to a
reason string, never an exception that takes a benchmark run down with it.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gm_llm import tokens  # noqa: E402

_COLS = ("tokens_input", "tokens_output", "tokens_reasoning",
         "tokens_cache_read", "tokens_cache_write")


def _store(path, rows, *, columns=_COLS, with_cost=True):
    """A fake opencode store. `rows` are (directory, agent, input, output, reasoning,
    cache_read, cache_write, cost)."""
    conn = sqlite3.connect(path)
    cost = ", cost REAL" if with_cost else ""
    conn.execute(f"create table session (id TEXT, directory TEXT, agent TEXT, "
                 f"{', '.join(f'{c} INTEGER' for c in columns)}{cost})")
    names = ["id", "directory", "agent", *columns] + (["cost"] if with_cost else [])
    for i, r in enumerate(rows):
        vals = (f"ses{i}", r[0], r[1]) + tuple(r[2:2 + len(columns)])
        if with_cost:
            vals += (r[-1],)
        conn.execute(f"insert into session ({', '.join(names)}) "
                     f"values ({', '.join('?' * len(names))})", vals)
    conn.commit()
    conn.close()


def test_usage_is_scoped_and_split_by_agent(tmp):
    run = tmp / "run-A"
    (run / ".opencode").mkdir(parents=True)
    other = tmp / "run-B"
    other.mkdir()
    db = tmp / "opencode.db"
    _store(db, [
        (str(run), "dm-runner", 100, 10, 5, 1000, 0, 0.5),
        (str(run / ".opencode"), "narrative-checker", 200, 20, 7, 2000, 3, 0.25),
        (str(run), "narrative-checker", 50, 5, 1, 500, 0, 0.25),
        (str(other), "dm-runner", 999, 999, 999, 999, 999, 9.0),   # a sibling run
        (str(tmp), "dm", 777, 777, 777, 777, 777, 7.0),            # the parent dir
    ])
    r = tokens.usage_for(run, db=db)
    assert r.unavailable is None, r.unavailable
    assert set(r.by_agent) == {"dm-runner", "narrative-checker"}, r.by_agent
    checker = r.by_agent["narrative-checker"]
    assert (checker.sessions, checker.input, checker.cache_write) == (2, 250, 3), \
        "a nested dir rolls into its run; agents aggregate"
    assert r.total.input == 350 and r.total.output == 35, "the sibling run is not counted"
    assert r.total.cache_read == 3500 and abs(r.total.cost - 1.0) < 1e-9
    assert r.total.uncached == 350 + 35 + 3, "uncached excludes cache reads"


def test_missing_store_and_schema_drift_degrade(tmp):
    r = tokens.usage_for(tmp / "run-A", data_dir=tmp / "nope")
    assert r.unavailable and "no opencode store" in r.unavailable
    assert r.total.input == 0, "an unreadable store reports nothing, not a confident zero"

    # opencode renames a column out from under us
    drifted = tmp / "opencode.db"
    _store(drifted, [], columns=("tokens_in", "tokens_out", "tokens_reasoning",
                                 "tokens_cache_read", "tokens_cache_write"))
    r = tokens.usage_for(tmp / "run-A", db=drifted)
    assert r.unavailable and "schema changed" in r.unavailable, r.unavailable

    # a store with no `cost` column still reports tokens
    nocost = tmp / "nocost.db"
    run = tmp / "run-A"
    run.mkdir(exist_ok=True)
    _store(nocost, [(str(run), "dm", 10, 1, 0, 100, 0, 0)], with_cost=False)
    r = tokens.usage_for(run, db=nocost)
    assert r.unavailable is None and r.total.input == 10 and r.total.cost == 0.0


def test_pricing_keeps_reasoning_separate(tmp):
    u = tokens.Usage(input=1_000_000, output=1_000_000, reasoning=500_000,
                     cache_read=10_000_000, cache_write=0)
    p = u.priced(0.14, 0.28, 0.0028)
    assert abs(p["input"] - 0.14) < 1e-9 and abs(p["output"] - 0.28) < 1e-9
    assert abs(p["cache_read"] - 0.028) < 1e-9
    assert abs(p["total"] - (0.14 + 0.28 + 0.028)) < 1e-9
    assert abs(p["reasoning_surcharge"] - 0.14) < 1e-9, \
        "reasoning is priced at the output rate but reported apart, never folded in"
    # cache writes default to the input rate, and take an override
    u2 = tokens.Usage(cache_write=1_000_000)
    assert abs(u2.priced(0.14, 0.28, 0.0028)["cache_write"] - 0.14) < 1e-9
    assert abs(u2.priced(0.14, 0.28, 0.0028, 1.0)["cache_write"] - 1.0) < 1e-9


def test_batch_keeps_the_instrument_out_of_play(tmp):
    out = tmp / "bench-out"
    run = out / "run-A"
    ws = out / "grade-ws" / "run-A"
    check_ws = out / "check-ws" / "run-A"
    for d in (run, ws, check_ws):
        d.mkdir(parents=True)
    db = tmp / "opencode.db"
    _store(db, [(str(run), "dm-runner", 1000, 100, 0, 10000, 0, 1.0),
                (str(check_ws), "play-checker", 200, 20, 0, 2000, 0, 0.0),
                (str(ws), "grader", 10, 1, 0, 100, 0, 0.01)])
    batch = tokens.usage_for_batch(out, db=db)
    assert set(batch["runs"]) == {"run-A"}, "the instrument workspaces are not runs"
    assert batch["runs"]["run-A"].total.input == 1000
    assert batch["checking"].total.input == 200
    assert batch["grading"].total.input == 10

    text = tokens.format_tokens(batch, prices=(0.14, 0.28, 0.0028))
    assert "run-A" in text and "grading" in text and "checking (check-ws)" in text
    assert "1,210" in text, "everything sums play, checking and grading"
    assert "$0.0001" in text or "$0.00" in text, "a cost table renders"
    assert "hypothetical cost" in text
    # and without prices there is no cost table at all — no invented dollars
    assert "hypothetical cost" not in tokens.format_tokens(batch)


def main():
    tests = (test_usage_is_scoped_and_split_by_agent, test_missing_store_and_schema_drift_degrade,
             test_pricing_keeps_reasoning_separate, test_batch_keeps_the_instrument_out_of_play)
    failures = 0
    for test in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"  ✓ {test.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"  ✗ {test.__name__}: {e}")
    print(f"\n{'FAIL' if failures else 'OK'} — {len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
