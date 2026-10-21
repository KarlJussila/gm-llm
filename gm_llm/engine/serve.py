"""
`gm-llm serve` — the engine over stdio: commands in on stdin, events out on stdout, one JSON
object per line. Logs and anything else that prints go to stderr. The engine closes when
stdin does, so a frontend that dies takes its engine with it.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading


def claim_stdout():
    """Take stdout for the protocol before anything can print to it: the real fd 1 is
    duplicated for the protocol writer, and fd 1 itself (and sys.stdout) now point at
    stderr. Returns the protocol stream."""
    out = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    sys.stdin.reconfigure(encoding="utf-8")
    return out


def fail(out, message: str) -> int:
    """The engine couldn't open: say why on the protocol and close."""
    for ev in ({"type": "error", "what": "opening the engine", "message": message},
               {"type": "state", "phase": "closed", "session": None, "awaiting": None,
                "busy": None, "player": None, "in_combat": False, "actions": []}):
        out.write(json.dumps(ev, ensure_ascii=False) + "\n")
    out.flush()
    return 1


def serve(engine, out) -> int:
    """Run `engine` over stdin and `out` (from `claim_stdout`) until stdin closes."""
    # The engine calls subscribers under its lock, so writing to a pipe the frontend is
    # slow to drain happens on a thread of its own.
    pending: queue.Queue = queue.Queue()

    def write() -> None:
        try:
            while (ev := pending.get()) is not None:
                out.write(json.dumps(ev, ensure_ascii=False) + "\n")
                out.flush()
        except OSError:
            pass  # the frontend is gone; stdin's end closes the engine

    writer = threading.Thread(target=write, daemon=True)
    writer.start()
    engine.subscribe(pending.put)
    engine.start()
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                cmd = json.loads(line)
            except ValueError as e:
                pending.put({"type": "error", "what": "command", "message": f"bad JSON: {e}"})
                continue
            engine.send(cmd)
            if cmd.get("type") == "shutdown":
                break
    finally:
        engine.close()
        pending.put(None)
        writer.join(timeout=5)
        try:
            out.close()
        except OSError:
            pass
    return 0
