#!/usr/bin/env python3
"""Standalone checks for the score-event archive (B0) — no pytest; run me directly.

Drives the real `Game` and `Planner` over minimal fakes (no opencode, no model)
and asserts the JSONL archive they leave behind: lazy `run` header, one `turn`
event per gated turn with the DRAFT preserved, one `stage` event per stage gate
with the as-checked artifact. This is the B0 exit criterion in miniature.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm import __version__  # noqa: E402
from gm_llm.orchestrator import Game, Logs, Planner  # noqa: E402
from gm_llm.orchestrator.archive import SCHEMA, Archive  # noqa: E402
from gm_llm.orchestrator.gate import StageGateResult, Verdict  # noqa: E402
from gm_llm.orchestrator.planner import planning_cut_off  # noqa: E402
from gm_llm.bench.workspace import turn_message  # noqa: E402


# ── fakes ───────────────────────────────────────────────────────────────────

class _Reply:
    rolls = ()

    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = set(tools)
        self.tool_inputs = tool_inputs or {}


class FakeBackend:
    """Just enough surface for Game/Planner: scripted draft replies, a scripted
    correction, and a context-usage stub. A draft item may be a plain string (text only)
    or a `_Reply` (to carry tool calls, e.g. task_complete)."""

    def __init__(self, directory, drafts):
        self.directory = str(directory)
        self.drafts = list(drafts)
        self.prompts = []  # (agent, message) of every prompt sent

    def create_session(self, title):
        return f"sid-{title}"

    def preface(self, sid, text):
        pass

    def prompt_full(self, sid, agent, message, whole=False):
        self.prompts.append((agent, message))
        item = self.drafts.pop(0)
        return item if isinstance(item, _Reply) else _Reply(item)

    def prompt(self, sid, agent, message, whole=False):
        self.prompts.append((agent, message))
        return "corrected narration"

    def ensure_tool(self, sid, agent, reply, *, tool, nudge, args=(), tries=1, whole=False):
        # Same logic as the real Backend.ensure_tool: no-op if the tool call is present,
        # else send the nudge and re-read, up to `tries` times.
        def satisfied(r):
            if tool not in r.tools:
                return False
            inp = r.tool_inputs.get(tool) or {}
            return all(str(inp.get(a, "")).strip() for a in args)

        for _ in range(tries):
            if satisfied(reply):
                break
            reply = self.prompt_full(sid, agent, nudge, whole=whole)
        return reply

    def context_usage(self, sid):
        class CU:
            tokens, context_limit, threshold = 1200, 100_000, 80_000
        return CU()


class FakeGate:
    """A scripted plan-gate verdict."""

    def __init__(self, results):
        self.results = list(results)

    def check_plan(self, plan, prologue=""):
        return StageGateResult(
            narrative=Verdict("check-plan", False, "1. Plan names an unknown NPC."),
            prompt="plan", label="Canon", canon_sections=3)


def _read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── tests ───────────────────────────────────────────────────────────────────

def test_archive_lazy_header(tmp):
    a = Archive.under(tmp)
    assert not a.path.exists(), "no file before the first emit"
    a.emit("turn", session=1, turn=1)
    events = _read_events(a.path)
    assert [e["event"] for e in events] == ["run", "turn"]
    head = events[0]
    assert head["run_id"] == a.run_id
    assert head["schema"] == SCHEMA
    assert head["gm_llm"] == __version__
    # Re-opening the same path appends without re-heading (a resumed run keeps one file).
    b = Archive(a.path, a.run_id)
    b.emit("turn", session=1, turn=2)
    assert [e["event"] for e in _read_events(a.path)] == ["run", "turn", "turn"]


def test_game_turn_events(tmp):
    logs = Logs.under(base=tmp / "logs")
    rolled = _Reply("His hair is grey.", ("dice",))
    rolled.rolls = ("d20 = 4",)
    backend = FakeBackend(tmp, drafts=[_Reply("The inn is warm.", ("skill", "read")), rolled])
    game = Game(backend, None, logs=logs, campaign_dir=str(tmp / "campaign"), session=1)
    game.start()
    tr = game.turn("I look at the barkeep.")
    assert tr.final == "His hair is grey."

    events = _read_events(logs.archive.path)
    assert [e["event"] for e in events] == ["run", "turn", "turn"]

    opening, turn = events[1], events[2]
    assert opening["opening"] and opening["turn"] == 1 and opening["session"] == 1
    assert opening["narration"] == "The inn is warm."
    assert opening["tools"] == ["read", "skill"]
    assert turn["turn"] == 2 and not turn["opening"]
    assert turn["player"] == "I look at the barkeep." and turn["narration"] == "His hair is grey."
    assert opening["rolls"] == [] and turn["rolls"] == ["d20 = 4"], "the DM's own rolls ride along"
    assert turn["tools"] == ["dice"] and turn["context"] == {"tokens": 1200, "limit": 100_000}
    assert "<rolls>d20 = 4</rolls>" in turn_message(turn) and "<rolls>" not in turn_message(opening)
    assert not ({"draft", "final", "verdicts", "corrected", "stale"} & turn.keys()), \
        "no in-loop check fields — checks run after play"


def test_planner_stage_event(tmp):
    logs = Logs.under(base=tmp / "logs")
    plan_path = tmp / "campaign" / "sessions" / "2" / "plan.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("# Session 2 plan\n", encoding="utf-8")

    backend = FakeBackend(tmp, drafts=[])
    Planner(backend, FakeGate([]), logs=logs).prep_session(2, commit=False)

    events = _read_events(logs.archive.path)
    assert [e["event"] for e in events] == ["run", "stage"]
    stage = events[1]
    assert stage["stage"] == "plan" and stage["session"] == 2
    assert not stage["verdict"]["passed"] and stage["corrected"] and not stage["committed"]
    assert stage["draft"] == "# Session 2 plan\n"  # the plan as gated, pre-correction
    assert not planning_cut_off(tmp, 2), "a finished plan leaves no planning marker"


def test_close_nudge(tmp):
    """A draft that ends the session in PROSE (a 'Session complete.' trailer) but skips
    task_complete gets one bounded nudge; when the call lands, the turn is session_complete
    and the archive turn event records `close_nudged`."""
    logs = Logs.under(base=tmp / "logs")
    backend = FakeBackend(tmp, drafts=[
        "The inn is warm.",                                          # opening
        _Reply("You slip out into the night.\n\n---\n*Session complete.*"),  # prose close, no tool
        _Reply("", tools=("task_complete",),                        # the nudge lands the call
               tool_inputs={"task_complete": {}}),
    ])
    game = Game(backend, None, logs=logs, campaign_dir=str(tmp / "campaign"), session=1)
    game.start()
    tr = game.turn("I head out for the night.")

    assert tr.close_nudged, "the prose-ending draft triggered a close nudge"
    assert tr.session_complete, "the nudge landed task_complete — the session is complete"
    assert tr.final == "You slip out into the night.\n\n---\n*Session complete.*", \
        "the original narration reaches the player, not the nudge reply"

    turn = _read_events(logs.archive.path)[-1]
    assert turn["event"] == "turn"
    assert turn["close_nudged"] is True and turn["session_complete"] is True


def test_no_nudge_on_ordinary_prose(tmp):
    """An ordinary narration (no bare end-of-session trailer) never triggers the nudge —
    if it did, the backend would be asked for a third reply and raise (only two scripted)."""
    logs = Logs.under(base=tmp / "logs")
    backend = FakeBackend(tmp, drafts=[
        "The inn is warm.",                                    # opening
        _Reply("Magren pours a drink and the session goes on, the night still young."),
    ])
    game = Game(backend, None, logs=logs, campaign_dir=str(tmp / "campaign"), session=1)
    game.start()
    tr = game.turn("I greet the barkeep.")

    assert not tr.close_nudged, "ordinary prose must not trigger the close nudge"
    assert not tr.session_complete
    assert not backend.drafts, "exactly the two scripted replies were consumed (no nudge)"
    assert _read_events(logs.archive.path)[-1]["close_nudged"] is False


def main():
    failures = 0
    for test in (test_archive_lazy_header, test_game_turn_events, test_planner_stage_event,
                 test_close_nudge, test_no_nudge_on_ordinary_prose):
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"  ✓ {test.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"  ✗ {test.__name__}: {e}")
    total = 5
    print(f"\n{'FAIL' if failures else 'OK'} — {total - failures}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
