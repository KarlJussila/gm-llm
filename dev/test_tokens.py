#!/usr/bin/env python3
"""Standalone checks for `gm-llm tokens` — no pytest; run me directly.

Builds a throwaway SQLite store shaped like opencode's `session` table and reads it back,
so the whole module is exercised with no opencode, no network, and no dependence on the
developer's real store. The point of most of these is the *failure* behaviour: this module
reads someone else's schema, so a missing store or a renamed column must degrade to a
reason string, never an exception that takes a benchmark run down with it.
"""

import json
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


# ── per session (opencode 2.x `session_v2` + `session_message`) ──────────────

T0 = 1_792_700_000_000  # ms


def _v2_store(path, directory):
    conn = sqlite3.connect(path)
    conn.execute("create table session_v2 (id TEXT, directory TEXT, agent TEXT, title TEXT, "
                 "time_created INTEGER, time_updated INTEGER, tokens_input INTEGER, "
                 "tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER)")
    conn.execute("create table session_message (id TEXT, session_id TEXT, type TEXT, "
                 "seq INTEGER, data TEXT)")
    conn.execute("insert into session_v2 values ('ses_a', ?, 'dm-runner', 'game', ?, ?, "
                 "100, 20, 30, 4000)", (str(directory), T0, T0 + 600_000))
    conn.execute("insert into session_v2 values ('ses_b', '/elsewhere', 'dm', 'x', ?, ?, "
                 "1, 1, 1, 1)", (T0, T0 + 1000))

    def step(created, secs, tools, text=None, ctx=(1000, 5000)):
        content = [{"type": "reasoning", "text": "**Weighing the door**"}]
        content += [{"type": "tool", "name": n,
                     # opencode keeps a big state as a JSON string, a small one inline
                     "state": json.dumps(s) if big else s} for n, s, big in tools]
        if text:
            content.append({"type": "text", "text": text})
        return {"time": {"created": created, "completed": created + secs * 1000},
                "tokens": {"input": ctx[0], "output": 40, "reasoning": 300,
                           "cache": {"read": ctx[1], "write": 0}},
                "content": content}

    msgs = [
        ("user", {"time": {"created": T0}, "text": "<player>Open the door</player>"}),
        ("assistant", step(T0 + 1000, 4, [
            ("skill", {"status": "completed", "input": {"id": "social-play"},
                       "content": [{"type": "text", "text": "x" * 50}]}, True),
            ("read", {"status": "error", "input": {"path": "feedback/social-play.md"},
                      "content": []}, False)])),
        ("assistant", step(T0 + 6000, 20, [], text="The door sticks, then gives.",
                           ctx=(2000, 9000))),
        # five minutes of player thinking before the next message
        ("user", {"time": {"created": T0 + 326_000}, "text": "<player>Go in</player>"}),
        ("assistant", step(T0 + 327_000, 6, [
            ("skill", {"status": "completed", "input": {"id": "social-play"},
                       "content": []}, False)], text="Dust.")),
    ]
    for i, (typ, data) in enumerate(msgs):
        conn.execute("insert into session_message values (?, 'ses_a', ?, ?, ?)",
                     (f"m{i}", typ, i, json.dumps(data)))
    conn.commit()
    conn.close()


def test_sessions_are_scoped_and_summarised(tmp):
    camp = tmp / "camp"
    camp.mkdir()
    db = tmp / "opencode.db"
    _v2_store(db, camp)
    sessions, reason = tokens.sessions_for(camp, db=db)
    assert reason is None, reason
    assert [s["id"] for s in sessions] == ["ses_a"], "only sessions under the directory"
    s = sessions[0]
    assert s["steps"] == 3
    assert s["model_s"] == 30, s["model_s"]
    assert s["peak_context"] == 11_000, "peak context is input + cache read of the biggest step"
    assert s["tool_errors"] == 1
    assert s["skills"] == ["social-play", "social-play"], "repeat loads are kept, not deduped"
    text = tokens.format_sessions(camp, sessions)
    assert "social-play ×2" in text and "11,000" in text


def test_timeline_reads_steps_tools_and_gaps(tmp):
    camp = tmp / "camp"
    camp.mkdir()
    db = tmp / "opencode.db"
    _v2_store(db, camp)
    text = tokens.format_timeline("ses_a", db=db)
    assert "Open the door" in text and "The door sticks" in text
    assert "→ skill social-play  [50 chars]" in text, "a JSON-string tool state is decoded"
    assert "✗ error" in text, "a failed tool call is flagged"
    assert "5.0 min idle" in text, "a long wait before a message is flagged"
    assert "Weighing the door" not in text, "reasoning headings only on request"
    assert "Weighing the door" in tokens.format_timeline("ses_a", db=db, reasoning=True)


def test_resolve_and_unreadable_store(tmp):
    sessions = [{"id": "ses_abc"}, {"id": "ses_abd"}, {"id": "ses_x"}]
    assert tokens.resolve(sessions, "2") == "ses_abd"
    assert tokens.resolve(sessions, "ses_x") == "ses_x"
    assert tokens.resolve(sessions, "ses_ab") is None, "an ambiguous prefix matches nothing"
    assert tokens.resolve(sessions, "9") is None

    _, reason = tokens.sessions_for(tmp, data_dir=tmp / "nope")
    assert reason and "no opencode store" in reason
    old = tmp / "opencode.db"
    sqlite3.connect(old).execute("create table session (id TEXT)").connection.close()
    _, reason = tokens.sessions_for(tmp, db=old)
    assert reason and "session_message" in reason, "a 1.x store gives a reason, not a crash"


def main():
    tests = (test_usage_is_scoped_and_split_by_agent, test_missing_store_and_schema_drift_degrade,
             test_pricing_keeps_reasoning_separate, test_batch_keeps_the_instrument_out_of_play,
             test_sessions_are_scoped_and_summarised, test_timeline_reads_steps_tools_and_gaps,
             test_resolve_and_unreadable_store)
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
