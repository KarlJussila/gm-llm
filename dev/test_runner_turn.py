#!/usr/bin/env python3
"""Standalone check for what the orchestrator sends the DM each turn and what it takes back
out. No pytest, no opencode, no model — run me directly.

  - a turn's message is the player's words, fenced, and nothing else (design/luna.md § Live
    play: no per-turn reminder);
  - the opening carries the prepared context in front of the kickoff;
  - the closing `task_complete` carries the closing narration (into the transcript) and the
    handoff notes (to `sessions/<n>/notes.md`), so the wrap needs no second call;
  - a turn whose last assistant message is a tool call still yields its narration.
"""

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import Game, paths  # noqa: E402
from gm_llm.orchestrator.backend import Backend, read_turn  # noqa: E402
from gm_llm.orchestrator.loop import join_narration, session_is_complete  # noqa: E402


class _Reply:
    rolls = ()

    def __init__(self, text, tools=(), tool_inputs=None):
        self.text = text
        self.tools = frozenset(tools)
        self.tool_inputs = tool_inputs or {}


class FakeBackend:
    """Scripted replies, with every message the DM was sent recorded."""

    def __init__(self, directory, replies):
        self.directory = str(directory)
        self.replies = list(replies)
        self.dm_msgs = []

    def create_session(self, title=None):
        return f"sid-{title}"

    def prompt_full(self, sid, agent, message, whole=False):
        self.dm_msgs.append(message)
        return self.replies.pop(0)

    def prompt(self, sid, agent, message, whole=False):
        return self.prompt_full(sid, agent, message, whole).text

    def ensure_tool(self, sid, agent, reply, **kw):
        return reply

    def patient(self, *a, **kw):
        from contextlib import nullcontext
        return nullcontext()

    def context_usage(self, sid):
        return None


class FakePreloader:
    def runner_preload(self, n):
        return "<prepared-context>\nTHE PLAN\n</prepared-context>\n\n"


def _game(tmp, replies, preloader=None):
    backend = FakeBackend(tmp, replies)
    (Path(tmp) / "campaign" / "sessions" / "1").mkdir(parents=True, exist_ok=True)
    return backend, Game(backend, preloader, session=1)


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def a_turn_is_the_player_and_nothing_else():
    tmp = tempfile.mkdtemp()
    backend, game = _game(tmp, [_Reply("The scene opens.")] + [_Reply("A beat.")] * 3,
                          preloader=FakePreloader())
    game.start()
    for _ in range(3):
        game.turn("I look around.")
    check(backend.dm_msgs[0] == "<prepared-context>\nTHE PLAN\n</prepared-context>\n\n"
          "Let's begin the session.", "the opening is the prepared context, then the kickoff")
    check(all(m == "<player>\nI look around.\n</player>" for m in backend.dm_msgs[1:]),
          "every turn's message is exactly the fenced player text")
    print("a_turn_is_the_player_and_nothing_else\n")


def the_closing_call_carries_narration_and_notes():
    tmp = tempfile.mkdtemp()
    closing = _Reply("", ("task_complete",), {"task_complete": {
        "player_message": "The lamps gutter as Brennan seals the shaft.",
        "notes": "Tarin is alive in the Wastes; Brennan evacuated the mine."}})
    backend, game = _game(tmp, [_Reply("The scene opens."), closing])
    game.start()
    tr = game.turn("We seal the mine.")
    camp = Path(tmp) / "campaign"
    check(tr.session_complete and tr.final == "The lamps gutter as Brennan seals the shaft.",
          "the closing narration comes back as the turn's narration")
    transcript = paths.transcript(camp, 1).read_text()
    check(transcript.rstrip().endswith("The lamps gutter as Brennan seals the shaft."),
          "…and closes the transcript (no empty final DM block)")
    notes = paths.notes(camp, 1).read_text()
    check("Tarin is alive in the Wastes" in notes, "the notes are filed from the same call")
    check(session_is_complete(tmp, 1), "the session is marked complete on disk")
    n_before = len(backend.dm_msgs)
    check(game.handoff() == paths.notes(camp, 1) and len(backend.dm_msgs) == n_before,
          "the wrap's handoff finds the notes already there and sends nothing")
    print("the_closing_call_carries_narration_and_notes\n")


def missing_notes_fall_back_to_one_request():
    tmp = tempfile.mkdtemp()
    closing = _Reply("You leave the mine behind.", ("task_complete",), {"task_complete": {}})
    notes = _Reply("", ("task_complete",), {"task_complete": {"notes": "Fallback notes."}})
    backend, game = _game(tmp, [_Reply("Opening."), closing, notes])
    game.start()
    tr = game.turn("We go.")
    check(tr.final == "You leave the mine behind.", "the reply text stands when no closing text")
    check(not paths.notes(Path(tmp) / "campaign", 1).exists(), "no notes yet")
    game.handoff()
    check("Fallback notes." in paths.notes(Path(tmp) / "campaign", 1).read_text(),
          "the fallback request files the notes")
    print("missing_notes_fall_back_to_one_request\n")


def join_narration_dedupes():
    check(join_narration("A.", "B.") == "A.\n\nB.", "text then closing")
    check(join_narration("A. B.", "B.") == "A. B.", "closing already inside the text")
    check(join_narration("", "B.") == "B.", "closing only")
    check(join_narration("A.", "") == "A.", "text only")
    print("join_narration_dedupes\n")


def a_turn_reads_back_whole():
    """A turn can span several assistant messages — narration, then a trailing tool call —
    and all of it comes back: the narration as the reply, the call as a signal."""
    tmp = tempfile.mkdtemp()
    scene = "The tavern falls quiet as the door swings shut."
    turn = [
        {"type": "assistant", "content": [{"type": "text", "text": scene}]},
        {"type": "assistant", "content": [{"type": "tool", "name": "task_complete",
                                           "state": {"input": {"notes": "n"}}}]},
        {"type": "idle", "outcome": "succeeded"},
    ]
    backend = Backend(directory=tmp, min_call_gap=0.0)
    backend._use_agent = lambda sid, agent: None
    backend._send = lambda sid, text: "msg_1"
    backend._await_turn = lambda sid, user_id: turn

    reply = backend.prompt_full("sid", "dm-runner", "go")
    check(reply.text == scene, "the narration before the trailing call is the reply")
    check(reply.tools == {"task_complete"} and reply.tool_inputs["task_complete"] == {"notes": "n"},
          "the trailing call is read as a signal")

    backend._await_turn = lambda sid, user_id: turn[1:]
    check(backend.prompt("sid", "narrative-checker", "go") == "",
          "a tool-call-only turn is a reply, not a failure to retry")
    print("a_turn_reads_back_whole\n")


def dice_calls_come_back_as_rolls():
    """Each completed dice call, in order, as "expression = total" — the shape opencode
    stores (the plugin's metadata carries the total)."""
    def dice(expr, total, status="completed"):
        return {"type": "tool", "name": "dice",
                "state": {"status": status, "input": {"expression": expr},
                          "metadata": {"total": total}}}
    tmp = tempfile.mkdtemp()
    turn = [
        {"type": "assistant", "content": [dice("d20+10", 20), dice("2d6", 7),
                                          dice("d4", None, status="error")]},
        {"type": "assistant", "content": [{"type": "text", "text": "The flecks hold still."}]},
        {"type": "idle", "outcome": "succeeded"},
    ]
    backend = Backend(directory=tmp, min_call_gap=0.0)
    backend._use_agent = lambda sid, agent: None
    backend._send = lambda sid, text: "msg_1"
    backend._await_turn = lambda sid, user_id: turn
    reply = backend.prompt_full("sid", "dm-runner", "go")
    check(reply.rolls == ("d20+10 = 20", "2d6 = 7"), f"completed rolls, in order: {reply.rolls}")
    print("dice_calls_come_back_as_rolls\n")


def a_final_answer_is_the_reply():
    """Seen in setup (luna7): the question said as commentary, a tool call, then said again
    as the final answer. Joined whole, the player read it twice."""
    q = "What kind of campaign would you like to play?"
    texts, calls, _ = read_turn([
        {"type": "assistant", "content": [
            {"type": "text", "text": q, "native": {"phase": "commentary"}},
            {"type": "tool", "name": "task_complete", "state": {"input": {}}}]},
        {"type": "assistant", "content": [
            {"type": "text", "text": q, "native": {"phase": "final_answer"}}]},
        {"type": "idle", "outcome": "succeeded"},
    ])
    check(texts == [q], "only the final answer is the reply")
    check([n for n, _ in calls] == ["task_complete"], "the tool call still comes back")
    texts, _, _ = read_turn([{"type": "assistant", "content": [
        {"type": "text", "text": "No phases here.", "native": {}}]}])
    check(texts == ["No phases here."], "a turn without a final answer reads as before")
    print("a_final_answer_is_the_reply\n")


def a_failed_turn_is_an_error():
    texts, calls, error = read_turn([
        {"type": "assistant", "content": [{"type": "text", "text": "partial"}]},
        {"type": "idle", "outcome": "failed", "error": {"message": "rate limited"}},
    ])
    check(error == "rate limited", "a failed idle surfaces its error")
    check(read_turn([{"type": "idle", "outcome": "interrupted"}])[2] == "turn interrupted",
          "an interrupted turn is an error too")
    print("a_failed_turn_is_an_error\n")


if __name__ == "__main__":
    a_final_answer_is_the_reply()
    a_turn_is_the_player_and_nothing_else()
    the_closing_call_carries_narration_and_notes()
    missing_notes_fall_back_to_one_request()
    join_narration_dedupes()
    a_turn_reads_back_whole()
    dice_calls_come_back_as_rolls()
    a_failed_turn_is_an_error()
    print("OK — runner turn: the message, the close, and the reply coming back whole.")
