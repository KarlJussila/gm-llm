#!/usr/bin/env python3
"""Standalone check for what the orchestrator puts in front of the runner each turn, and
what it takes back out. No pytest, no opencode, no model — run me directly.

Both halves exist because of one measured fact (`design/runner-authority.md` § Delivery):
across five pilot runs the runner loaded its skills and read canon on turn 1 and never
again, in sessions that ran past turn 40 — so a *standing* instruction to re-load is read
as already satisfied, and by turn 24 the campaign is being narrated from memory.

  - the per-turn brief carries a staleness line the orchestrator computes, not the prose:
    it appears only once the runner has gone `_STALE_AFTER_TURNS` turns without opening a
    skill or a campaign file, and it carries the count so the pressure escalates;
  - any lookup — `skill`, `read`, `grep`, `glob` — resets it;
  - and, the consequence of handing the runner a task list at all: a turn whose LAST
    assistant message is a tool call still yields its narration. opencode splits a turn at
    each tool call and the POST returns only that last message, so a runner that writes
    the scene and then touches its list would otherwise hand the gate an empty draft.
"""

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import Game  # noqa: E402
from gm_llm.orchestrator.backend import Backend  # noqa: E402
from gm_llm.orchestrator.gate import GateResult, Verdict  # noqa: E402
from gm_llm.orchestrator.loop import _STALE_AFTER_TURNS  # noqa: E402


# ── fakes ─────────────────────────────────────────────────────────────────────

class _Reply:
    def __init__(self, text, tools=()):
        self.text = text
        self.tools = frozenset(tools)
        self.tool_inputs = {}


class FakeBackend:
    """Scripted drafts, with every message the RUNNER was sent recorded — this file's
    whole subject is that message."""

    def __init__(self, directory, drafts):
        self.directory = str(directory)
        self.drafts = list(drafts)
        self.i = 0
        self.dm_msgs = []

    def create_session(self, title=None):
        return f"sid-{title}"

    def prompt_full(self, sid, agent, message, whole=False):
        self.dm_msgs.append(message)
        text, tools = self.drafts[self.i]
        self.i += 1
        return _Reply(text, tools)

    def prompt(self, sid, agent, message, whole=False):
        self.dm_msgs.append(message)
        return "corrected."

    def context_usage(self, sid):
        return None


class FakeGate:
    def check(self, narration, player_msg, in_combat=False):
        return GateResult(Verdict("check-turn", True, ""), Verdict("check-conduct", True, ""),
                          player_msg, canon_sections=0)


def _game(backend):
    return Game(backend, FakeGate(), campaign_dir=backend.directory, session=1, transcript=False)


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


# ── scenarios ─────────────────────────────────────────────────────────────────

def the_brief_rides_every_turn():
    """The invariant the loop has always had: the per-turn algorithm is in front of every
    player message, and its placeholders are filled — never emitted raw."""
    tmp = tempfile.mkdtemp()
    backend = FakeBackend(tmp, [("A beat.", ())] * 3)
    game = _game(backend)
    for _ in range(3):
        game.turn("I look around.")

    for i, msg in enumerate(backend.dm_msgs, 1):
        check("<turn-reminder>" in msg, f"turn {i} carries the brief")
        check("todowrite" in msg, f"turn {i} opens the turn with the task list")
        check("{" not in msg.split("<player>")[0],
              f"turn {i}'s brief has no unfilled placeholder left in it")
    check(backend.dm_msgs[0].endswith("<player>\nI look around.\n</player>"),
          "the player's own words close the message, fenced")
    print("the_brief_rides_every_turn: the algorithm and the fence, every turn.\n")


def the_staleness_line_appears_only_when_it_is_true():
    """Silence while the runner is still looking things up; a line naming the count once it
    has stopped. A line that only appears when true is the point — the static version of it
    has ridden every turn since the pivot and stopped being acted on after turn 1."""
    tmp = tempfile.mkdtemp()
    n = _STALE_AFTER_TURNS
    backend = FakeBackend(tmp, [("A beat.", ())] * (n + 2))
    game = _game(backend)
    for _ in range(n + 2):
        game.turn("I keep talking.")

    quiet, first, second = backend.dm_msgs[:n], backend.dm_msgs[n], backend.dm_msgs[n + 1]
    check(all("STALE" not in m for m in quiet),
          f"the first {n} turns say nothing — the runner is inside its budget")
    check("STALE" in first, f"turn {n + 1} — {n} turns without a lookup — says so")
    check(f"{n} turns since" in first, "…and names the count")
    check(f"{n + 1} turns since" in second, "…which keeps climbing while it is ignored")
    check(first.index("STALE") < first.index("<turn-reminder>") + 40,
          "the line leads the brief, not buried in it")
    print("the_staleness_line_appears_only_when_it_is_true: quiet, then escalating.\n")


def any_lookup_resets_it():
    """`skill`, `read`, `grep`, `glob` — a re-load or a canon read both count as looking
    something up. Rolling dice or hitting the combat tracker does not."""
    tmp = tempfile.mkdtemp()
    n = _STALE_AFTER_TURNS
    for tool in ("skill", "read", "grep", "glob"):
        backend = FakeBackend(tmp, [("A beat.", ())] * (n - 1) + [("A beat.", (tool,))]
                              + [("A beat.", ())] * n)
        game = _game(backend)
        for _ in range(2 * n):
            game.turn("I keep talking.")
        check(all("STALE" not in m for m in backend.dm_msgs),
              f"a `{tool}` call on turn {n} resets the count — no line in {2 * n} turns")

    backend = FakeBackend(tmp, [("A beat.", ("dice",))] * (n + 1))
    game = _game(backend)
    for _ in range(n + 1):
        game.turn("I keep talking.")
    check("STALE" in backend.dm_msgs[n], "rolling dice is not looking anything up")
    print("any_lookup_resets_it: the reset is a lookup, not any tool call.\n")


def narration_before_a_trailing_tool_call_is_not_lost():
    """The hazard a per-turn task list introduces: the model writes the scene and then
    touches a tool. opencode splits the turn there and the POST returns only the last
    message — so the draft must be recovered from history, or the player gets a blank."""
    tmp = tempfile.mkdtemp()
    scene = "The tavern falls quiet as the door swings shut."
    history = [
        {"info": {"role": "user"}, "parts": [{"type": "text", "text": "<turn-reminder>…"}]},
        {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": scene}]},
        {"info": {"role": "assistant"},
         "parts": [{"type": "tool", "tool": "todowrite", "state": {"input": {"todos": []}}}]},
    ]
    tool_only = {"parts": [{"type": "tool", "tool": "todowrite"}]}

    backend = Backend(directory=tmp, min_call_gap=0.0)
    backend._raw_get = lambda path, timeout=30: history
    backend._post_watched = lambda path, body, session_id: tool_only

    check(backend._run_prompt("sid", "dm-runner", "go") == scene,
          "the stranded narration comes back as the draft")

    # …while a turn that genuinely produced only a tool call is still a legitimate reply,
    # not a failure to retry (a checker submitting report_findings and nothing else).
    backend._raw_get = lambda path, timeout=30: history[:1] + history[2:]
    check(backend._run_prompt("sid", "narrative-checker", "go") == "",
          "a genuinely text-free turn still returns empty rather than retrying")
    print("narration_before_a_trailing_tool_call_is_not_lost: no blank scenes.\n")


if __name__ == "__main__":
    the_brief_rides_every_turn()
    the_staleness_line_appears_only_when_it_is_true()
    any_lookup_resets_it()
    narration_before_a_trailing_tool_call_is_not_lost()
    print("OK — runner turn: the brief, the staleness line, and the draft coming back whole.")
