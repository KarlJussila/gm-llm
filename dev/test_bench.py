#!/usr/bin/env python3
"""Standalone checks for the bench runner (B1) — no pytest; run me directly.

Exercises run-dir assembly, the conditions event, the play loop, the turn cap, and
batch resilience over fakes for the expensive seams (Backend, Gate, reconcile) so it
needs no network, no npm, and no opencode. Mirrors dev/test_archive.py's style — the
same _Reply / gate-verdict fakes, tempdirs, and a hand-rolled runner over asserts.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.bench import runner  # noqa: E402
from gm_llm.orchestrator.gate import GateResult, Verdict  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = frozenset(tools)
        self.tool_inputs = tool_inputs or {}


class FakeBackend:
    """A play backend that never touches opencode: scripted runner drafts (with an
    optional `task_complete` at a chosen player turn), a canned player line, and a
    context-usage stub below the wrap threshold. `start`/`stop` are counted no-ops."""

    def __init__(self, directory, *, complete_after=None):
        self.directory = str(directory)
        self.base = "http://fake"
        self.complete_after = complete_after  # player-turn index that wraps, or None
        self._runner_calls = 0
        self.started = self.stopped = 0
        self.on_retry = None

    def start(self):
        self.started += 1
        return self

    def stop(self):
        self.stopped += 1

    def create_session(self, title=None):
        return f"sid-{title}"

    def prompt_full(self, sid, agent, message, whole=False):
        if whole:  # the handoff call — always closes with its notes
            return _Reply("notes", tools={"task_complete"},
                          tool_inputs={"task_complete": {"notes": "handoff notes"}})
        self._runner_calls += 1  # 1 = opening, 2 = player turn 1, …
        complete = (self.complete_after is not None
                    and self._runner_calls == self.complete_after + 1)
        return _Reply("The tavern is warm.", tools={"task_complete"} if complete else ())

    def prompt(self, sid, agent, message, whole=False):
        return "I look around."

    def ensure_tool(self, sid, agent, reply, **kw):
        return reply

    def context_usage(self, sid):
        class CU:
            tokens, context_limit, threshold = 1000, 100_000, 80_000
        return CU()


class FakeGate:
    """Always-clean verdicts, so the loop never triggers a correction pass."""

    def check(self, narration, player_msg, in_combat=False):
        return GateResult(Verdict("check-turn", True, ""),
                          Verdict("check-conduct", True, ""),
                          player_msg, canon_sections=7)


AGENTS = {
    "dm-runner": ("opencode/mimo-v2.5-free", "0.3"),
    "player": ("opencode/mimo-v2.5-free", "0.8"),
    "narrative-checker": ("opencode/mimo-v2.5-free", "0.1"),
    "dm": ("opencode/mimo-v2.5-free", "0.2"),
}


def _make_template(root):
    """A minimal template project: `.opencode/agent/*.md` with model+temperature
    frontmatter (what the conditions event parses)."""
    agent_dir = root / ".opencode" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    for name, (model, temp) in AGENTS.items():
        (agent_dir / f"{name}.md").write_text(
            f"---\nmode: primary\nmodel: {model}\ntemperature: {temp}\n---\nbody\n",
            encoding="utf-8")
    return root


def _make_fixture(root, *, fixture_id="hollowfell-test"):
    """A minimal fixture dir: fixture.json + a campaign/ with a session-1 plan and a
    character packet (mirrors the shipped hollowfell fixture's shape)."""
    campaign = root / "campaign"
    (campaign / "sessions").mkdir(parents=True, exist_ok=True)
    (campaign / "documents").mkdir(parents=True, exist_ok=True)
    (campaign / "sessions" / "session-1-plan.md").write_text("# Session 1 plan\n", encoding="utf-8")
    (campaign / "documents" / "pc.md").write_text(
        "# Dallid\n<!-- a spoiler comment -->\nA wandering cleric.\n", encoding="utf-8")
    (root / "fixture.json").write_text(json.dumps({
        "id": fixture_id, "frozen": "2026-07-17", "provisional": True,
        "character_packet": "campaign/documents/pc.md",
    }), encoding="utf-8")
    return root


def _fakes(*, complete_after=None, reconcile_calls=None):
    """A factory bundle wiring the fakes into run_once/run_batch, recording reconcile
    invocations into `reconcile_calls` if given."""
    def backend_factory(directory, **kw):
        return FakeBackend(directory, complete_after=complete_after)

    def gate_factory(backend, directory, logs):
        return FakeGate()

    def reconcile_fn(backend, gate, logs, n):
        if reconcile_calls is not None:
            reconcile_calls.append(n)

    return dict(backend_factory=backend_factory, gate_factory=gate_factory,
                reconcile_fn=reconcile_fn, note=lambda m: None)


def _archive_events(run_dir):
    hits = sorted((Path(run_dir) / ".opencode" / "logs").glob("archive-*.jsonl"))
    assert hits, "no archive left behind"
    return [json.loads(line) for line in hits[-1].read_text(encoding="utf-8").splitlines()]


# ── tests ──────────────────────────────────────────────────────────────────────

def test_assemble_run(tmp):
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    assert (run_dir / "campaign" / "sessions" / "session-1-plan.md").is_file(), "campaign copied"
    assert (run_dir / ".opencode" / "agent" / "dm-runner.md").is_file(), "template copied"
    assert (run_dir / ".git").is_dir(), "git repo initialized"
    assert ".opencode/" in (run_dir / ".gitignore").read_text(encoding="utf-8"), ".opencode gitignored"
    # exactly one commit, and .opencode excluded from it
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=run_dir,
                           capture_output=True, text=True)
    assert count.stdout.strip() == "1", f"expected one commit, got {count.stdout!r}"
    tracked = subprocess.run(["git", "ls-files"], cwd=run_dir, capture_output=True, text=True).stdout
    assert "campaign/sessions/session-1-plan.md" in tracked
    assert ".opencode/" not in tracked, ".opencode must be gitignored, not committed"


def test_conditions_event(tmp):
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=5,
                          **_fakes(complete_after=1))
    events = _archive_events(run_dir)
    assert events[0]["event"] == "run", "run header first"
    cond = events[1]
    assert cond["event"] == "conditions", "conditions rides right behind the header"
    assert cond["fixture"]["id"] == "hollowfell-test" and cond["fixture"]["provisional"] is True
    assert cond["tier"] == "low" and cond["turn_cap"] == 5 and cond["reconcile"] is True
    dmr = cond["agents"]["dm-runner"]
    assert dmr["model"] == "opencode/mimo-v2.5-free" and dmr["temperature"] == 0.3
    assert cond["agents"]["player"]["temperature"] == 0.8


def test_natural_close(tmp):
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    reconciled = []
    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=30,
                          **_fakes(complete_after=1, reconcile_calls=reconciled))
    assert rec["outcome"] == "complete", rec
    assert rec["turns"] == 1, f"closed on turn 1, before the cap — got {rec['turns']}"
    assert reconciled == [1], f"reconcile ran for session 1 — got {reconciled}"
    # no cap event on a clean close
    assert not any(e["event"] == "cap" for e in _archive_events(run_dir))


def test_cap_breach_skips_reconcile(tmp):
    out = tmp / "out"
    _make_template(out / "template")  # pre-seed so prepare_template reuses (no init/install)
    fixture = _make_fixture(tmp / "fixture")

    reconciled = []
    records = runner.run_batch(
        fixture, out, runs=1, turn_cap=3,
        init=lambda d: None, install=lambda d: (True, "noop"),
        **_fakes(complete_after=None, reconcile_calls=reconciled))

    assert records[0]["outcome"] == "cap" and records[0]["turns"] == 3, records
    assert reconciled == [], "reconcile must be skipped on a cap breach"
    run_dir = out / records[0]["run_dir"]
    cap = [e for e in _archive_events(run_dir) if e["event"] == "cap"]
    assert cap and cap[0]["turn"] == 3, f"cap event with the turn number — got {cap}"
    # the manifest recorded it
    manifest = [json.loads(l) for l in (out / "batch.jsonl").read_text().splitlines()]
    assert len(manifest) == 1 and manifest[0]["outcome"] == "cap"


def test_failed_run_survives_batch(tmp):
    from gm_llm.orchestrator import BackendError
    out = tmp / "out"
    _make_template(out / "template")
    fixture = _make_fixture(tmp / "fixture")

    calls = {"n": 0}

    def flaky_backend(directory, **kw):
        calls["n"] += 1
        b = FakeBackend(directory, complete_after=1)
        if calls["n"] == 1:  # first run's backend dies on boot (a rate-limit give-up)
            def boom():
                raise BackendError("rate limited")
            b.start = boom
        return b

    records = runner.run_batch(
        fixture, out, runs=2, turn_cap=5,
        init=lambda d: None, install=lambda d: (True, "noop"),
        backend_factory=flaky_backend,
        gate_factory=lambda backend, directory, logs: FakeGate(),
        reconcile_fn=lambda *a: None, note=lambda m: None)

    assert len(records) == 2, "the batch kept going after the failure"
    assert records[0]["outcome"].startswith("failed:"), records[0]
    assert records[1]["outcome"] == "complete", records[1]
    manifest = [json.loads(l) for l in (out / "batch.jsonl").read_text().splitlines()]
    assert len(manifest) == 2, "both runs recorded in the manifest"


def main():
    tests = (test_assemble_run, test_conditions_event, test_natural_close,
             test_cap_breach_skips_reconcile, test_failed_run_survives_batch)
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
