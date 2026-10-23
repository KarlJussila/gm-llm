#!/usr/bin/env python3
"""Standalone check for the backend's retry ladder: a cut-off attempt is resumed, not reverted —
the retry asks the agent to carry on in the same session, the reply counts the tools of the whole
exchange, and each failed attempt lands in the archive. Only a give-up rolls the exchange back.
No pytest, no opencode — run me directly."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator import Logs  # noqa: E402
from gm_llm.orchestrator.backend import Backend, BackendError  # noqa: E402
from gm_llm.orchestrator.prompts import load  # noqa: E402


class _NoWait:
    """Stands in for the cancel event so the backoff doesn't sleep."""
    def clear(self): pass
    def is_set(self): return False
    def wait(self, _): return False
    def set(self): pass


def _assistant(*content):
    return {"type": "assistant", "content": list(content)}


def _tool(name, **inp):
    return {"type": "tool", "name": name, "state": {"status": "completed", "input": inp}}


IDLE = {"type": "idle", "outcome": "succeeded"}
CUT = {"type": "idle", "outcome": "interrupted"}


def _backend(root: Path, attempts: list[list[dict]]) -> tuple[Backend, dict]:
    """A Backend whose server is a script: attempt i's turn is `attempts[i]`."""
    b = Backend(str(root), logs=Logs.under(root / "logs"), retries=3)
    seen = {"sent": [], "reverted": [], "session": []}
    b._cancel = _NoWait()
    b._pace = lambda: None
    b._use_agent = lambda sid, agent: None

    def send(sid, text):
        seen["sent"].append(text)
        uid = f"u{len(seen['sent'])}"
        seen["session"] += [{"type": "user", "id": uid}, *attempts[len(seen["sent"]) - 1]]
        return uid

    def turn(sid, uid):
        ids = [m.get("id") for m in seen["session"]]
        return seen["session"][ids.index(uid) + 1:]

    b._send = send
    b._await_turn = turn
    b._turn = turn
    b._revert_to = lambda sid, uid: seen["reverted"].append(uid) or True
    return b, seen


def t_resumes_after_a_cut_off_attempt(root: Path) -> None:
    b, seen = _backend(root, [
        [_assistant(_tool("dice", expression="1d20"), {"type": "text", "text": "The lock"}), CUT],
        [_assistant({"type": "text", "text": "The lock gives."}, _tool("task_complete", summary="done")), IDLE],
    ])
    retries = []
    b.on_retry = lambda *a: retries.append(a)
    reply = b.prompt_full("s1", "dm-runner", "I pick the lock.")
    assert seen["sent"] == ["I pick the lock.", load("continue-interrupted")], seen["sent"]
    assert seen["reverted"] == [], "a retry keeps the cut-off attempt"
    assert reply.text == "The lock gives."
    assert reply.tools == {"dice", "task_complete"}, "tools count across the whole exchange"
    assert retries and retries[0][3] == "turn interrupted"
    events = [json.loads(line) for line in b.logs.archive.path.read_text().splitlines()]
    retry = [e for e in events if e["event"] == "retry"]
    assert len(retry) == 1 and retry[0]["agent"] == "dm-runner" and retry[0]["session_id"] == "s1"
    assert b.revert_exchange("s1") and seen["reverted"] == ["u1"], "a cancel reverts the whole exchange"


def t_gives_up_and_rolls_back(root: Path) -> None:
    b, seen = _backend(root, [[CUT], [CUT], [CUT]])
    try:
        b.prompt("s1", "dm", "Build the world.")
        raise AssertionError("three cut-off attempts give up")
    except BackendError:
        pass
    assert seen["sent"][1:] == [load("continue-interrupted")] * 2
    assert seen["reverted"] == ["u1"], "a give-up takes the exchange back out"
    assert not b.revert_exchange("s1"), "and leaves nothing for the caller to revert twice"


def main() -> None:
    tests = [t_resumes_after_a_cut_off_attempt, t_gives_up_and_rolls_back]
    for t in tests:
        with tempfile.TemporaryDirectory(prefix="gm-retry-") as temp:
            t(Path(temp))
    print(f"OK — {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
