#!/usr/bin/env python3
"""Standalone checks for the bench runner (B1) — no pytest; run me directly.

Exercises run-dir assembly, the conditions event, the play loop, the turn cap, and
batch resilience over fakes for the expensive seams (Backend, Gate, the lifecycle's
between-session pass) so it needs no network, no npm, and no opencode. Mirrors
dev/test_archive.py's style — the same _Reply / gate-verdict fakes, tempdirs, and a
hand-rolled runner over asserts.
"""

import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

import copy  # noqa: E402

from gm_llm.bench import runner  # noqa: E402
from gm_llm.orchestrator import Lifecycle  # noqa: E402
from gm_llm.orchestrator.combat import CombatState  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    rolls = ()

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

    @contextmanager
    def patient(self, stall_timeout, retries=None):  # real Backend widens budget & cuts retries; no-op here
        yield

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
    """Play runs no checks; the lifecycle only reaches for the preloader."""

    preloader = None


class CombatFakeBackend:
    """A play backend that also drives a scripted COMBAT episode through run_once: its
    dm-runner beats mutate the tracker state file the way the real plugin's tool calls
    would, so the bench's combat handoff (`play_combat`) runs end to end. The turn pointer
    in the state file disambiguates a PC-slot draft (`combat_player_action`) from an NPC
    beat (`combat_step`) — the same signal the real Game reads.

    `end_after` ends the fight (an NPC beat calls `end_encounter`) once that many PC slots
    have been played; None never ends it (to exercise a cap breach mid-fight)."""

    def __init__(self, directory, *, end_after=1):
        self.directory = str(directory)
        self.base = "http://fake"
        self.started = self.stopped = 0
        self.on_retry = None
        self._st = CombatState(directory)
        self._calls = 0
        self._end_after = end_after
        self._pc_slots = 0

    def start(self):
        self.started += 1
        return self

    def stop(self):
        self.stopped += 1

    def create_session(self, title=None):
        return f"sid-{title}"

    @contextmanager
    def patient(self, stall_timeout, retries=None):  # real Backend widens budget & cuts retries; no-op here
        yield

    def prompt(self, sid, agent, message, whole=False):
        return "I strike the nearest foe and hold my ground."

    def context_usage(self, sid):
        class CU:
            tokens, context_limit, threshold = 1000, 100_000, 80_000
        return CU()

    def ensure_tool(self, sid, agent, reply, **kw):
        return reply

    def _seed(self):
        frame = {
            "turn": "pc", "round": 1,
            "combatants": {
                "pc": {"id": "pc", "name": "PC", "hp": 30, "hp_max": 30, "dead": False,
                       "conditions": [], "reaction": True, "x": 0, "y": 0, "z": 0},
                "goblin-1": {"id": "goblin-1", "name": "goblin", "hp": 12, "hp_max": 12,
                             "dead": False, "conditions": [], "reaction": True,
                             "x": 15, "y": 0, "z": 0},
            },
            "initiative": ["pc", "goblin-1"], "timers": [],
        }
        self._st.save({"encounter": "ambush", "next_timer_id": 1,
                       "committed": copy.deepcopy(frame), "pending": copy.deepcopy(frame)})

    def _act(self, target, amount):
        s = self._st.load()
        c = s["pending"]["combatants"][target]
        c["hp"] = max(0, c["hp"] - amount)
        init = s["pending"]["initiative"]
        ni = (init.index(s["pending"]["turn"]) + 1) % len(init)
        if ni == 0:
            s["pending"]["round"] += 1
        s["pending"]["turn"] = init[ni]
        # A confirmed turn commits; the bench auto-confirms every NPC beat, and the PC beat
        # commits directly — so harden immediately, keeping committed == pending between beats.
        s["committed"] = copy.deepcopy(s["pending"])
        self._st.save(s)

    def prompt_full(self, sid, agent, message, whole=False):
        if whole:  # the handoff call
            return _Reply("notes", tools={"task_complete"},
                          tool_inputs={"task_complete": {"notes": "handoff notes"}})
        self._calls += 1
        if self._calls == 1:  # the opening scene
            return _Reply("The tavern is warm and loud.")
        if not self._st.exists():
            if self._calls == 2:  # first turn: a fight breaks out
                self._seed()
                return _Reply("Steel rings free — roll initiative!", tools={"start_encounter"})
            # a post-combat turn: wrap the session
            return _Reply("You bind your wounds and rest.", tools={"task_complete"},
                          tool_inputs={"task_complete": {"notes": "n"}})
        # In combat: the turn pointer says whose beat this is.
        if self._st.turn == "pc":
            self._pc_slots += 1
            self._act("goblin-1", 5)
            return _Reply(f"You strike (slot {self._pc_slots}).",
                          tools={"damage", "advance_turn"})
        if self._end_after is not None and self._pc_slots >= self._end_after:
            self._st.delete()
            return _Reply("The foe breaks and flees into the night.", tools={"end_encounter"})
        self._act("pc", 3)
        return _Reply("The goblin lunges at you.", tools={"damage", "advance_turn"})


def _lifecycle_factory(on_reconcile=None):
    """The real `Lifecycle` — the interface bench plays through — with only its expensive
    seam stood in for. `Game`, the player source and the warm-runner handoff stay real (the
    resume tests turn on exactly those); `reconcile` is recorded via `on_reconcile(n)`,
    which may also raise to simulate a post-wrap give-up."""
    class _FakeLifecycle(Lifecycle):
        def reconcile(self, n, on_stage=None, commit=True):
            if on_stage:
                on_stage("digest")  # the real pipeline's first stage tick
            if on_reconcile is not None:
                on_reconcile(n)

    def factory(backend, gate, directory, logs):
        return _FakeLifecycle(backend, gate, str(directory), logs=logs, player="auto")

    return factory


def _combat_fakes(*, end_after=1, reconcile_calls=None):
    def backend_factory(directory, **kw):
        return CombatFakeBackend(directory, end_after=end_after)

    def gate_factory(backend, directory, logs):
        return FakeGate()

    return dict(backend_factory=backend_factory, gate_factory=gate_factory,
                lifecycle_factory=_lifecycle_factory(
                    None if reconcile_calls is None else reconcile_calls.append),
                note=lambda m: None)


AGENTS = {
    "dm-runner": ("openai/gpt-6-luna", "xhigh"),
    "dm": ("openai/gpt-6-luna", "xhigh"),
    "helper": ("openai/gpt-6-luna", "xhigh"),
    "log-extractor": ("openai/gpt-6-luna", "xhigh"),
    "narrative-checker": ("openai/gpt-6-luna", "high"),
    "player": ("openai/gpt-6-luna", "medium"),
}


def _make_template(root):
    """A minimal template project: `.opencode/agent/*.md` with model and variant
    frontmatter (what the conditions event parses)."""
    agent_dir = root / ".opencode" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    for name, (model, variant) in AGENTS.items():
        (agent_dir / f"{name}.md").write_text(
            f"---\nmode: primary\nmodel: {model}\nvariant: {variant}\n---\nbody\n",
            encoding="utf-8")
    return root


def _make_fixture(root, *, fixture_id="hollowfell-test"):
    """A minimal fixture dir: fixture.json + a campaign/ with a session-1 plan and a PC
    sheet to generate the packet from (mirrors the shipped hollowfell fixture's shape)."""
    campaign = root / "campaign"
    (campaign / "sessions" / "1").mkdir(parents=True, exist_ok=True)
    (campaign / "characters").mkdir(parents=True, exist_ok=True)
    (campaign / "sessions" / "1" / "plan.md").write_text("# Session 1 plan\n", encoding="utf-8")
    (campaign / "characters" / "dallid.md").write_text(
        "---\nslug: dallid\nname: Dallid\ntype: pc\nstatus: active\n---\n# Dallid\n\n"
        "## Personality\nA wandering cleric.\n\n"
        "## Character hooks (DM-side)\nA spoiler hook.\n", encoding="utf-8")
    (root / "story.md").write_text("<!-- reviewer's note -->\nLast time, a storm.\n",
                                   encoding="utf-8")
    (root / "fixture.json").write_text(json.dumps({
        "id": fixture_id, "frozen": "2026-07-17", "provisional": True,
    }), encoding="utf-8")
    return root


def _fakes(*, complete_after=None, reconcile_calls=None):
    """A factory bundle wiring the fakes into run_once/run_batch, recording reconcile
    invocations into `reconcile_calls` if given."""
    def backend_factory(directory, **kw):
        return FakeBackend(directory, complete_after=complete_after)

    def gate_factory(backend, directory, logs):
        return FakeGate()

    return dict(backend_factory=backend_factory, gate_factory=gate_factory,
                lifecycle_factory=_lifecycle_factory(
                    None if reconcile_calls is None else reconcile_calls.append),
                note=lambda m: None)


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

    assert (run_dir / "campaign" / "sessions" / "1" / "plan.md").is_file(), "campaign copied"
    assert (run_dir / ".opencode" / "agent" / "dm-runner.md").is_file(), "template copied"
    assert (run_dir / ".git").is_dir(), "git repo initialized"
    assert ".opencode/" in (run_dir / ".gitignore").read_text(encoding="utf-8"), ".opencode gitignored"
    # exactly one commit, and .opencode excluded from it
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=run_dir,
                           capture_output=True, text=True)
    assert count.stdout.strip() == "1", f"expected one commit, got {count.stdout!r}"
    tracked = subprocess.run(["git", "ls-files"], cwd=run_dir, capture_output=True, text=True).stdout
    assert "campaign/sessions/1/plan.md" in tracked
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
    assert dmr == {"model": "openai/gpt-6-luna", "variant": "xhigh"}, dmr
    assert cond["agents"]["player"]["variant"] == "medium"
    assert set(cond["agents"]) == set(AGENTS), "every agent a run can call is stamped"
    assert cond["subagents"] == "sequential", "the subagents mode is part of the condition"
    assert cond["prompts"]["sha256"] and cond["prompts"]["files"] >= len(AGENTS), \
        f"the prose the run played under is fingerprinted — got {cond['prompts']}"


def test_subject_model(tmp):
    """`--subject-model` moves the subject agents and nothing else: the checker and the
    autoplayer are the instrument and the player, pinned on their own."""
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test",
                        subject_model="opencode/mimo-v2.6-flash-free", subject_variant="")
    agents = runner.agent_conditions(run_dir)
    for name in ("dm-runner", "dm", "helper", "log-extractor"):
        assert agents[name] == {"model": "opencode/mimo-v2.6-flash-free", "variant": None}, \
            (name, agents[name])
    assert agents["narrative-checker"] == {"model": "openai/gpt-6-luna", "variant": "high"}
    assert agents["player"] == {"model": "openai/gpt-6-luna", "variant": "medium"}
    body = (run_dir / ".opencode" / "agent" / "dm.md").read_text(encoding="utf-8")
    assert body.endswith("---\nbody\n"), "the prompt body is untouched"


def test_prompt_fingerprint(tmp):
    """The fingerprint covers the prose a run actually played under, is stable across calls,
    and moves on any content or path change — otherwise a prompt edit would silently pool
    with the batch that preceded it."""
    run_dir = _make_template(tmp / "run")
    (run_dir / ".opencode" / "skills" / "session-close").mkdir(parents=True)
    skill = run_dir / ".opencode" / "skills" / "session-close" / "SKILL.md"
    skill.write_text("# close\nstep 5\n", encoding="utf-8")

    base = runner.prompt_fingerprint(run_dir)
    assert base["sha256"] and base["files"] > len(AGENTS), base
    assert runner.prompt_fingerprint(run_dir) == base, "stable across calls"

    skill.write_text("# close\nstep 5, reworded\n", encoding="utf-8")
    edited = runner.prompt_fingerprint(run_dir)
    assert edited["sha256"] != base["sha256"], "a prose edit must move the hash"
    assert edited["files"] == base["files"], "same file count, different content"

    # a rename is a different prompt even at identical bytes (skills load by name)
    skill.write_text("# close\nstep 5\n", encoding="utf-8")
    assert runner.prompt_fingerprint(run_dir) == base, "reverting the text reverts the hash"
    skill.rename(skill.parent / "SKILL-renamed.md")
    assert runner.prompt_fingerprint(run_dir)["sha256"] != base["sha256"], "path feeds the digest"


def test_prompt_change_is_a_mixed_condition(tmp):
    """Two runs that agree on fixture/tier/models but disagree on prose are NOT one batch —
    the report must refuse to pool them, since the prose is what tier 0 measures."""
    from gm_llm.bench import scoring
    cond = {"event": "conditions", "fixture": {"id": "hollowfell"}, "tier": "low",
            "turn_cap": 50, "agents": {"dm": {"model": "m", "variant": "xhigh"}}}
    a = scoring._condition_signature({**cond, "prompts": {"sha256": "aaaa", "files": 9}})
    b = scoring._condition_signature({**cond, "prompts": {"sha256": "bbbb", "files": 9}})
    assert scoring._identity(a) != scoring._identity(b), "different prose = different condition"
    assert scoring._identity(a) == scoring._identity(
        scoring._condition_signature({**cond, "prompts": {"sha256": "aaaa", "files": 9}}))
    # archives written before the fingerprint existed carry nothing and still pool together
    old = scoring._condition_signature(cond)
    assert old["prompts"] is None and scoring._identity(old) == scoring._identity(
        scoring._condition_signature(dict(cond))), "unstamped archives stay comparable"


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


def test_post_wrap_is_lifecycle_wrap(tmp):
    """The post-wrap tail is `Lifecycle.wrap`, not a private Game+Reconciler wiring: it
    captures the warm runner's handoff notes AND reports its stages through `on_stage` —
    the protocol a watching frontend renders."""
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    notes, reconciled = [], []
    fakes = _fakes(complete_after=1, reconcile_calls=reconciled)
    fakes["note"] = notes.append
    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=30, **fakes)

    assert rec["outcome"] == "complete" and reconciled == [1], (rec, reconciled)
    assert (run_dir / "campaign" / "sessions" / "1" / "notes.md").is_file(), \
        "wrap() captures the warm runner's handoff notes before the between-session pass"
    assert "reconcile: handoff…" in notes and "reconcile: digest…" in notes, \
        f"the wrap's stage ticks reach the run's progress notes — got {notes}"


def test_player_source_comes_from_the_lifecycle(tmp):
    """The autoplayer is `Lifecycle.player_source()`, so a bench run and `play --player
    auto` prime the character packet by construction rather than by two matching spellings
    of the same bracketed heading."""
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    said = []

    class Recording(FakeBackend):
        def prompt(self, sid, agent, message, whole=False):
            said.append((agent, message))
            return "I look around."

    fakes = _fakes(complete_after=2)
    fakes["backend_factory"] = lambda directory, **kw: Recording(directory, complete_after=2)
    runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=30, **fakes)

    player = [m for agent, m in said if agent == "player"]
    assert len(player) == 2, f"two player turns before the wrap — got {len(player)}"
    assert "# You are Dallid" in player[0] and "A wandering cleric." in player[0], \
        f"the packet generated from the PC sheet primes the first message — got {player[0]!r}"
    assert "spoiler hook" not in player[0], "the sheet's DM-side hooks stay out of the packet"
    assert "Last time, a storm." in player[0] and "reviewer's note" not in player[0], \
        "the fixture's recap primes the first message, its comment stripped"
    assert "# You are Dallid" not in player[1], "the packet is handed over once, not per turn"


def test_post_wrap_reconcile_failure_stays_complete(tmp):
    """A stall in the post-wrap reconcile (a rate limit, or a slow large-input call the
    retries gave up on) must NOT demote a naturally-wrapped run: play is the measured
    subject and it's settled. Otherwise the archive would say complete while the manifest
    said incomplete, and `--resume` (which classifies from the archive) would strand it."""
    from gm_llm.orchestrator import BackendError
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    fakes = _fakes(complete_after=1)
    def boom(n):
        raise BackendError("log-extractor failed after 4 retries")
    fakes["lifecycle_factory"] = _lifecycle_factory(boom)

    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=30, **fakes)
    assert rec["outcome"] == "complete", f"wrapped run must stay complete — got {rec}"
    assert rec["turns"] == 1, f"turn count must survive the reconcile failure — got {rec}"
    # archive agrees on play, and flags the tail: complete (so no turn is ever replayed)
    # but reconcile-pending (so the sweep comes back to finish it).
    state, _ = runner.classify_archive(rec["archive"])
    assert state == "complete", f"archive must classify complete — {state}"
    assert runner.reconcile_pending(rec["archive"]), \
        "a reconcile that never gated must stay visible to --resume, not be stranded"


def test_batch_status(tmp):
    """`bench status` sorts a batch's runs the way `--resume` classifies them, the last
    manifest line winning for a run that was resumed."""
    turn = {"event": "turn", "session_complete": False}
    wrap = {"event": "turn", "session_complete": True}
    runs = {
        "run-a": [{"event": "conditions", "reconcile": True}, turn, wrap,
                  {"event": "stage", "stage": "propagation"}, {"event": "stage", "stage": "plan"}],
        "run-b": [{"event": "conditions", "reconcile": True}, turn, wrap],
        "run-c": [{"event": "conditions", "reconcile": True}, turn],
        "run-d": [{"event": "conditions", "reconcile": True}, turn, {"event": "cap"}],
    }
    lines = []
    for rd, events in runs.items():
        (tmp / rd).mkdir()
        (tmp / rd / "archive.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        lines.append({"run_dir": rd, "archive": f"{rd}/archive.jsonl"})
    lines.insert(0, {"run_dir": "run-a", "archive": None})  # superseded by its resume
    (tmp / "batch.jsonl").write_text("\n".join(json.dumps(r) for r in lines) + "\n",
                                     encoding="utf-8")
    assert runner.batch_status(tmp) == {"complete": ["run-a"], "reconcile pending": ["run-b"],
                                        "resumable": ["run-c"], "capped": ["run-d"]}
    assert runner.batch_status(tmp / "nowhere") == {}


def test_reconcile_pending(tmp):
    """The post-wrap gap is read off the `plan` stage event — the next session's prep, the pass's
    last step —
    and only under a condition that asked for reconcile at all."""
    def arc(events):
        p = tmp / f"rp-{len(list(tmp.glob('rp-*')))}.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return p

    assert runner.reconcile_pending(tmp / "nope.jsonl") is False
    wrap = {"event": "turn", "session_complete": True}
    # asked for reconcile, never reached the gate → pending
    assert runner.reconcile_pending(arc([{"event": "conditions", "reconcile": True}, wrap]))
    # died mid-pipeline: earlier stages archived, propagation never did → still pending
    assert runner.reconcile_pending(arc([
        {"event": "conditions", "reconcile": True}, wrap,
        {"event": "stage", "stage": "digest"}, {"event": "stage", "stage": "lint"}]))
    # propagation gated but the next plan never came → still pending (a usage limit during prep)
    assert runner.reconcile_pending(arc([
        {"event": "conditions", "reconcile": True}, wrap,
        {"event": "stage", "stage": "propagation"}]))
    # the next session planned → the pass got all the way through; nothing owed
    assert not runner.reconcile_pending(arc([
        {"event": "conditions", "reconcile": True}, wrap,
        {"event": "stage", "stage": "propagation"}, {"event": "stage", "stage": "plan"}]))
    # --play-only never wanted a reconcile; its absence is not a gap
    assert not runner.reconcile_pending(arc([{"event": "conditions", "reconcile": False}, wrap]))


def test_resume_finishes_reconcile_only(tmp):
    """A wrapped run whose reconcile the rate limits ate is picked up by `--resume` and
    finished WITHOUT replaying a turn — play is settled, only the tail re-runs."""
    from gm_llm.orchestrator import BackendError
    out = tmp / "out"
    _make_template(out / "template")
    fixture = _make_fixture(tmp / "fixture")
    state = {"draft": 0, "complete_on": {2}}  # opening=1, turn1 draft=2 wraps
    calls = []

    def fakes(on_reconcile):
        return dict(
            init=lambda d: None,
            backend_factory=lambda directory, **kw: ScriptedBackend(directory, state),
            gate_factory=lambda backend, directory, logs: FakeGate(),
            lifecycle_factory=_lifecycle_factory(on_reconcile), note=lambda m: None)

    def boom(n):
        calls.append(("boom", n))
        raise BackendError("narrative-checker failed after 2 retries")

    first = runner.run_batch(fixture, out, runs=1, turn_cap=10, **fakes(boom))
    assert first[0]["outcome"] == "complete" and first[0]["turns"] == 1, first
    run_dir = out / first[0]["run_dir"]
    played = sum(1 for e in _archive_events(run_dir) if e["event"] == "turn")

    def ok(n):
        calls.append(("ok", n))

    resumed = runner.run_batch(fixture, out, turn_cap=10, resume=True, **fakes(ok))
    assert len(resumed) == 1, f"the wrapped-but-unreconciled run is resumable — got {resumed}"
    assert resumed[0]["outcome"] == "complete", resumed
    assert resumed[0]["turns"] == 1, f"a wrapped session must not grow turns — got {resumed[0]}"
    assert calls == [("boom", 1), ("ok", 1)], f"reconcile retried once, no replay — {calls}"

    # still one archive, still one turn: the resume added no play and no second stream
    hits = sorted((run_dir / ".opencode" / "logs").glob("archive-*.jsonl"))
    assert len(hits) == 1, f"resume appends to the run's own archive — got {hits}"
    ev = _archive_events(run_dir)
    assert sum(1 for e in ev if e["event"] == "turn") == played, "no turn replayed or added"
    assert sum(1 for e in ev if e["event"] == "conditions") == 1, "conditions not re-emitted"


def test_cap_breach_skips_reconcile(tmp):
    out = tmp / "out"
    _make_template(out / "template")  # pre-seed so prepare_template reuses (no init)
    fixture = _make_fixture(tmp / "fixture")

    reconciled = []
    records = runner.run_batch(
        fixture, out, runs=1, turn_cap=3,
        init=lambda d: None,
        **_fakes(complete_after=None, reconcile_calls=reconciled))

    assert records[0]["outcome"] == "cap" and records[0]["turns"] == 3, records
    assert reconciled == [], "reconcile must be skipped on a cap breach"
    run_dir = out / records[0]["run_dir"]
    cap = [e for e in _archive_events(run_dir) if e["event"] == "cap"]
    assert cap and cap[0]["turn"] == 3, f"cap event with the turn number — got {cap}"
    # the manifest recorded it
    manifest = [json.loads(l) for l in (out / "batch.jsonl").read_text().splitlines()]
    assert len(manifest) == 1 and manifest[0]["outcome"] == "cap"


def test_combat_natural_close(tmp):
    """A fight breaks out on turn 1, runs through the CombatDriver, and the session then
    wraps — proving the bench loop enters combat, exits it, and resumes normal play. The
    combat PC slot counts against the cap (turns: 1 entry + 1 PC slot + 1 wrap turn = 3)."""
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    reconciled = []
    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=30,
                          **_combat_fakes(end_after=1, reconcile_calls=reconciled))
    assert rec["outcome"] == "complete", rec
    assert rec["turns"] == 3, f"1 entry + 1 combat PC slot + 1 wrap turn — got {rec['turns']}"
    assert reconciled == [1], f"reconcile ran for session 1 — got {reconciled}"
    assert not any(e["event"] == "cap" for e in _archive_events(run_dir)), "no cap breach"


def test_combat_cap_breach(tmp):
    """A fight that never ends must not make a run uncappable: each PC slot burns a turn,
    the hard cap trips, and the run is a cap breach (reconcile skipped, `cap` event
    stamped) — the same safety net as a non-combat run that never wraps."""
    template = _make_template(tmp / "template")
    fixture = _make_fixture(tmp / "fixture")
    run_dir = tmp / "run"
    runner.assemble_run(template, fixture / "campaign", run_dir, "hollowfell-test")

    reconciled = []
    rec = runner.run_once(run_dir, runner.load_fixture(fixture), turn_cap=3,
                          **_combat_fakes(end_after=None, reconcile_calls=reconciled))
    assert rec["outcome"] == "cap", rec
    assert rec["turns"] == 3, f"the fight ran into the cap — got {rec['turns']}"
    assert reconciled == [], "reconcile must be skipped on a cap breach mid-combat"
    cap = [e for e in _archive_events(run_dir) if e["event"] == "cap"]
    assert cap and cap[0]["turn"] == 3, f"cap event with the turn number — got {cap}"


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
        init=lambda d: None,
        backend_factory=flaky_backend,
        gate_factory=lambda backend, directory, logs: FakeGate(),
        lifecycle_factory=_lifecycle_factory(), note=lambda m: None)

    assert len(records) == 2, "the batch kept going after the failure"
    assert records[0]["outcome"].startswith("failed:"), records[0]
    assert records[1]["outcome"] == "complete", records[1]
    manifest = [json.loads(l) for l in (out / "batch.jsonl").read_text().splitlines()]
    assert len(manifest) == 2, "both runs recorded in the manifest"


class ScriptedBackend:
    """A play backend whose runner drafts are scripted by a *shared* state dict so behavior
    spans the two backend instances a fail-then-resume run makes (a new backend is built per
    run_once). `state["boom"]` is the set of global draft indices that raise `BackendError`
    (a rate-limit give-up); `state["complete_on"]` the ones that emit `task_complete`.
    `session_valid` returns False so resume takes the durable re-prime path."""

    def __init__(self, directory, state):
        self.directory = str(directory)
        self.base = "http://fake"
        self.state = state
        self.started = self.stopped = 0
        self.on_retry = None

    def start(self):
        self.started += 1
        return self

    def stop(self):
        self.stopped += 1

    def create_session(self, title=None):
        return f"sid-{title}"

    @contextmanager
    def patient(self, stall_timeout, retries=None):  # real Backend widens budget & cuts retries; no-op here
        yield

    def session_valid(self, sid):
        return False

    def prompt_full(self, sid, agent, message, whole=False):
        if whole:  # handoff — returns before counting a draft
            return _Reply("notes", tools={"task_complete"},
                          tool_inputs={"task_complete": {"notes": "handoff notes"}})
        self.state["draft"] += 1
        n = self.state["draft"]
        if n in self.state.get("boom", ()):
            from gm_llm.orchestrator import BackendError
            raise BackendError("rate limited")
        complete = n in self.state.get("complete_on", ())
        return _Reply("The tavern is warm.", tools={"task_complete"} if complete else ())

    def prompt(self, sid, agent, message, whole=False):
        return "I look around."

    def ensure_tool(self, sid, agent, reply, **kw):
        return reply

    def context_usage(self, sid):
        class CU:
            tokens, context_limit, threshold = 1000, 100_000, 80_000
        return CU()


def test_classify_archive(tmp):
    def arc(events):
        p = tmp / f"a-{len(list(tmp.glob('a-*')))}.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return p

    assert runner.classify_archive(tmp / "nope.jsonl") == ("empty", 0)
    assert runner.classify_archive(arc([{"event": "run"}, {"event": "conditions"}])) == ("empty", 0)
    # turns, no wrap, no cap → resumable
    assert runner.classify_archive(arc([
        {"event": "turn", "session_complete": False},
        {"event": "turn", "session_complete": False}])) == ("resumable", 2)
    # last turn wraps → complete
    assert runner.classify_archive(arc([
        {"event": "turn", "session_complete": False},
        {"event": "turn", "session_complete": True}])) == ("complete", 2)
    # a cap event → capped, terminal
    assert runner.classify_archive(arc([
        {"event": "turn", "session_complete": False}, {"event": "cap", "turn": 1}])) == ("capped", 1)


def test_rate_limit_is_incomplete_not_failed(tmp):
    """A backend give-up *mid-play* (turns already landed) is recorded `incomplete`, not
    `failed`, and leaves its archive on disk — the transcript is the resume point."""
    out = tmp / "out"
    _make_template(out / "template")
    fixture = _make_fixture(tmp / "fixture")
    state = {"draft": 0, "boom": {3}}  # opening=1, turn1=2 land; turn2 draft=3 gives up

    records = runner.run_batch(
        fixture, out, runs=1, turn_cap=10,
        init=lambda d: None,
        backend_factory=lambda directory, **kw: ScriptedBackend(directory, state),
        gate_factory=lambda backend, directory, logs: FakeGate(),
        lifecycle_factory=_lifecycle_factory(), note=lambda m: None)

    assert records[0]["outcome"].startswith("incomplete:"), records[0]
    assert records[0]["turns"] == 2, f"two turns landed before the give-up — got {records[0]}"
    run_dir = out / records[0]["run_dir"]
    ev = _archive_events(run_dir)
    assert sum(1 for e in ev if e["event"] == "turn") == 2, "the two landed turns are archived"
    assert not any(e["event"] == "cap" for e in ev), "an interrupt is not a cap breach"


def test_resume_continues_incomplete_run(tmp):
    """`run_batch(resume=True)` picks the incomplete run back up, continues in the SAME
    archive (one file, one conditions event, a resume marker, continuous turn ids), wraps,
    reconciles, and updates the manifest line in place (one line per run, outcome flipped)."""
    out = tmp / "out"
    _make_template(out / "template")
    fixture = _make_fixture(tmp / "fixture")
    # opening=1, turn1=2 land; turn2 draft=3 gives up. On resume: draft 4 lands, draft 5 wraps.
    state = {"draft": 0, "boom": {3}, "complete_on": {5}}
    reconciled = []

    def fakes(**over):
        return dict(
            init=lambda d: None,
            backend_factory=lambda directory, **kw: ScriptedBackend(directory, state),
            gate_factory=lambda backend, directory, logs: FakeGate(),
            lifecycle_factory=_lifecycle_factory(reconciled.append),
            note=lambda m: None, **over)

    first = runner.run_batch(fixture, out, runs=1, turn_cap=10, **fakes())
    assert first[0]["outcome"].startswith("incomplete:"), first[0]
    run_dir = out / first[0]["run_dir"]

    resumed = runner.run_batch(fixture, out, turn_cap=10, resume=True, **fakes())
    assert len(resumed) == 1 and resumed[0]["outcome"] == "complete", resumed
    assert resumed[0]["turns"] == 4, f"2 on disk + 2 more to the wrap — got {resumed[0]}"
    assert reconciled == [1], f"reconcile ran once, for session 1 — got {reconciled}"

    # one archive file, appended (not a fresh one): a single conditions event, a resume marker
    hits = sorted((run_dir / ".opencode" / "logs").glob("archive-*.jsonl"))
    assert len(hits) == 1, f"resume must append to the run's own archive — got {hits}"
    ev = _archive_events(run_dir)
    assert sum(1 for e in ev if e["event"] == "conditions") == 1, "conditions not re-emitted"
    assert any(e["event"] == "resume" for e in ev), "a resume marker is stamped"
    turns = [e for e in ev if e["event"] == "turn"]
    assert len(turns) == 4 and turns[-1]["session_complete"], f"4 continuous turns, last wraps — {turns}"
    assert [t["turn"] for t in turns] == [1, 2, 3, 4], f"turn ids continue past the break — {turns}"

    # manifest collapsed to one line for the run, outcome flipped to complete
    manifest = [json.loads(l) for l in (out / "batch.jsonl").read_text().splitlines() if l.strip()]
    assert len(manifest) == 1 and manifest[0]["outcome"] == "complete", manifest


def test_resume_noop_when_nothing_incomplete(tmp):
    """Resume over a batch with no incompletes does nothing (and doesn't crash on a fresh out)."""
    out = tmp / "out"
    _make_template(out / "template")
    fixture = _make_fixture(tmp / "fixture")
    records = runner.run_batch(fixture, out, resume=True, note=lambda m: None,
                               init=lambda d: None)
    assert records == [], "nothing to resume over an empty/complete batch"


def test_run_exit_code(tmp):
    """`bench run` exits non-zero unless every run finished, so `bench run && bench check`
    stops at a run that still needs `--resume`."""
    import argparse
    from gm_llm.bench import cli

    def arc(name, events):
        p = tmp / name
        p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return name

    wrap = {"event": "turn", "session_complete": True}
    done = arc("done.jsonl", [{"event": "conditions", "reconcile": True}, wrap,
                              {"event": "stage", "stage": "plan"}])
    held = arc("held.jsonl", [{"event": "conditions", "reconcile": True}, wrap])
    args = argparse.Namespace(turn_timeout=0, play_only=False, resume=False, runs=1, fixture="f",
                              out=str(tmp), ui="console", turn_cap=50, tier="low",
                              subject_model=None, subject_variant=None, kickoff=None, port=0,
                              min_gap=0, stream=False)

    def code(records):
        real = runner.run_batch
        runner.run_batch = lambda *a, **kw: records
        try:
            cli.cmd_bench_run(args)
        except SystemExit as e:
            return e.code
        finally:
            runner.run_batch = real

    assert code([{"outcome": "complete", "archive": done}, {"outcome": "cap"}]) == 0
    assert code([{"outcome": "complete", "archive": done},
                 {"outcome": "incomplete: player failed after 4 retries"}]) == 1
    assert code([{"outcome": "complete", "archive": held}]) == 1, "reconcile pending isn't done"
    assert code([{"outcome": "failed: boom"}]) == 1


def main():
    tests = (test_assemble_run, test_conditions_event, test_subject_model, test_prompt_fingerprint,
             test_prompt_change_is_a_mixed_condition, test_natural_close,
             test_post_wrap_is_lifecycle_wrap, test_player_source_comes_from_the_lifecycle,
             test_post_wrap_reconcile_failure_stays_complete,
             test_cap_breach_skips_reconcile, test_combat_natural_close,
             test_combat_cap_breach, test_failed_run_survives_batch,
             test_classify_archive, test_batch_status, test_reconcile_pending,
             test_rate_limit_is_incomplete_not_failed,
             test_resume_continues_incomplete_run, test_resume_finishes_reconcile_only,
             test_resume_noop_when_nothing_incomplete, test_run_exit_code)
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
