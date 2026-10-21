#!/usr/bin/env python3
"""Standalone check for the ENGINE and its protocol (design/frontends.md). No pytest, no
opencode, no model — run me directly.

The engine runs over `MockLifecycle` and is driven only through commands, the way any
frontend drives it, and what is asserted is the event stream:

  - setup → plan session 1 → play, with `awaiting` and `actions` saying at each point what
    a line of input is and which commands are accepted; a command not offered is refused
    with an `error` and changes nothing;
  - a fight: the PC's action, a bare confirm, a reaction to an NPC beat, back to the table;
  - a meta question between turns;
  - a cancel mid-turn hands the message back and leaves the session playing;
  - `advance` during play takes the loop down, wraps, and offers the next session;
  - the same protocol over a real `gm-llm serve` child: JSON lines both ways, and the child
    is gone after `close`.
"""

import queue
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.engine.core import Engine  # noqa: E402
from gm_llm.engine.client import LocalClient, ProcessClient  # noqa: E402
from gm_llm.orchestrator.mock import MockLifecycle  # noqa: E402


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


class Driver:
    """Reads a client's events, keeping what arrived since the last `until`."""

    def __init__(self, client):
        self.client = client
        self.seen = []
        self.state = {}

    def send(self, type_, text=None):
        cmd = {"type": type_} if text is None else {"type": type_, "text": text}
        self.client.send(cmd)

    def until(self, what, timeout=10.0, **want):
        """Collect events until a `state` matching `want`; return the events seen on the way."""
        self.seen = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ev = self.client.events.get(timeout=0.1)
            except queue.Empty:
                continue
            self.seen.append(ev)
            if ev["type"] == "state":
                self.state = ev
                if all(ev.get(k) == v for k, v in want.items()):
                    print(f"  ok: {what}")
                    return self.seen
        print(f"FAIL: timed out waiting for {what} ({want}); last state {self.state}")
        sys.exit(1)

    def said(self, speaker=None):
        return [e for e in self.seen if e["type"] == "say"
                and (speaker is None or e["speaker"] == speaker)]

    def of(self, type_):
        return [e for e in self.seen if e["type"] == type_]


def _local(pace=0.0, setup=False):
    return Driver(LocalClient(Engine(MockLifecycle(start_in_setup=setup, pace=pace))))


def setup_then_play():
    print("setup_then_play:")
    d = _local(setup=True)
    d.until("setup opens awaiting an answer", phase="setup", awaiting="answer")
    check(d.seen[0]["type"] == "hello" and d.seen[0]["protocol"] == 1, "hello comes first")
    check(d.state["actions"] == ["status", "shutdown", "input"],
          "an answer is the only play-shaped command in setup")
    check(d.said("dm"), "the DM's opening question is said")

    d.send("advance")
    ev = d.client.events.get(timeout=2)
    check(ev["type"] == "error" and ev["what"] == "advance", "a command not offered is refused")

    for i in range(2):
        d.send("input", f"answer {i}")
        d.until(f"answer {i} is taken", awaiting="answer")
        check(d.said("player")[0]["text"] == f"answer {i}", f"answer {i} is echoed")
    d.send("input", "my character")
    d.until("the last answer completes setup", phase="setup_done")
    check([e["key"] for e in d.of("stage")] == ["arcs-state", "lint", "gate", "commit"],
          "setup's stages are announced with their keys")
    check(d.state["actions"] == ["status", "shutdown", "advance"],
          "at setup_done the next step is an advance")

    d.send("advance")
    d.until("session 1 opens awaiting a turn", phase="play", awaiting="turn")
    check(any(e["type"] == "state" and e["phase"] == "planning" for e in d.seen),
          "planning comes between")
    check("meta" in d.state["actions"] and "advance" in d.state["actions"],
          "between turns: input, meta, or wrap")
    d.client.close()
    d.until("close ends the engine", phase="closed")
    print()


def a_fight():
    print("a_fight:")
    d = _local()
    d.until("play opens", awaiting="turn")
    d.send("input", "I look around")
    d.until("a turn plays", awaiting="turn")
    check([e["speaker"] for e in d.said()] == ["player", "dm"], "the turn: echo, then the DM")
    check(d.of("turn")[0]["n"] == 1, "the turn's tool summary is numbered")

    d.send("input", "I draw steel")
    d.until("the fight reaches the PC's slot", awaiting="pc_action", in_combat=True)
    check("advance" not in d.state["actions"], "no wrap mid-fight")
    d.send("input", "I strike")
    d.until("an NPC beat awaits confirm", awaiting="confirm")
    check([e["combatant"] for e in d.said("dm")] == ["pc", "thug-1"],
          "combat beats name their combatant")
    d.send("input", "")
    d.until("a bare input confirms", awaiting="confirm")
    d.send("input", "I raise my shield")
    d.until("a reaction replays the beat", awaiting="confirm")
    check(d.said("player")[0]["text"] == "I raise my shield", "the reaction is echoed")
    d.send("input", "")
    d.until("the fight ends", awaiting="turn", in_combat=False)
    check(any(e["type"] == "notice" and "fight is over" in e["text"] for e in d.seen),
          "the end of the fight is noticed")

    d.send("meta", "how long left?")
    d.until("a meta question is answered", awaiting="turn")
    check([e["meta"] for e in d.said()] == [True, True], "both sides of it are marked meta")
    d.client.close()
    print()


def cancel_hands_back():
    print("cancel_hands_back:")
    d = _local(pace=1.0)
    d.until("play opens", awaiting="turn", timeout=15)
    d.send("input", "I look around")
    d.until("the turn is in flight", busy="the DM is writing")
    check("cancel" in d.state["actions"], "a call in flight can be cancelled")
    d.send("cancel")
    d.until("the loop asks again", awaiting="turn")
    check([e["text"] for e in d.of("handback")] == ["I look around"],
          "the cancelled message comes back")
    check(not d.said("dm"), "the cancelled turn produced no narration")
    d.client.close()
    print()


def advance_wraps():
    print("advance_wraps:")
    d = _local()
    d.until("play opens", awaiting="turn")
    d.send("advance")
    d.until("the wrap finishes and offers the next session", phase="ready")
    check(not any(e["type"] == "state" and e["phase"] == "play" and e["awaiting"]
                  for e in d.seen), "no input is offered once the wrap is asked for")
    check([e["key"] for e in d.of("stage")][-1] == "prep", "the wrap's stages run to prep")
    d.send("advance")
    d.until("session 2 opens", phase="play", awaiting="turn", session=2)
    d.client.close()
    print()


def over_the_pipe():
    print("over_the_pipe:")
    client = ProcessClient(["serve", "--mock"])
    d = Driver(client)
    d.until("the engine speaks JSON lines from a child process", awaiting="turn", timeout=30)
    d.send("input", "I look around")
    d.until("a turn round-trips", awaiting="turn")
    check([e["speaker"] for e in d.said()] == ["player", "dm"], "events arrive in order")
    client.close()
    d.until("shutdown closes it", phase="closed")
    check(client._proc.poll() is not None, "the child has exited")
    print()


if __name__ == "__main__":
    setup_then_play()
    a_fight()
    cancel_hands_back()
    advance_wraps()
    over_the_pipe()
    print("OK — engine: setup, play, combat, meta, cancel, wrap, and the stdio protocol.")
