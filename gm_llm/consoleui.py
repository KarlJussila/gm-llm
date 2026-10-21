"""
The console frontend — a plain prompt over the engine protocol (design/frontends.md).

Reads events off the client and prints them; when the engine is waiting on the player and
nothing else is queued, asks for a line. Ctrl+C while the table works cancels the call in
flight; at the prompt, or on end of input, it quits.

Commands at the prompt: `/meta <question>`, `/wrap`, `/status`, `/roll <dice>`, `/quit`.
"""

from __future__ import annotations

import queue
import sys

from .dice import roll_expr

_ASK = {
    "setup_done": "Setup complete — plan and start session 1?",
    "ready": "Session {n} planned — start playing it?",
    "complete": "Session {n} complete — reconcile and prep session {next}?",
    # play with nothing awaited and nothing in flight: the loop stopped (a cap, a failure)
    "play": "The session has stopped — wrap it now?",
}


def _print(text: str = "", *, err: bool = False) -> None:
    print(text, file=sys.stderr if err else sys.stdout, flush=True)


def _render(ev: dict, *, stream: bool, human: bool) -> None:
    kind = ev["type"]
    if kind == "say":
        if ev["speaker"] == "player":
            if not human:
                _print(f"\nPLAYER\n{ev['text']}")
            return
        label = "DM (out of game)" if ev.get("meta") else "DM"
        if ev.get("combatant"):
            label = f"⚔ {'you' if ev['combatant'] == 'pc' else ev['combatant']}"
        _print(f"\n{label}\n{ev['text']}")
    elif kind == "notice":
        _print(f"— {ev['text']} —")
    elif kind in ("stage", "progress"):
        _print(f"  ▸ {ev['label']}…")
    elif kind == "error":
        _print(f"! {ev['what']} failed: {ev['message']}")
    elif kind == "handback":
        _print(f"— cancelled — your message was: {ev['text']}")
    elif kind == "retry":
        _print(f"  ({ev['agent']} call failed: {ev['reason']} — retry {ev['attempt']} "
               f"in {ev['wait']}s)", err=True)
    elif kind == "status":
        _print(f"campaign: {ev['root']} · phase {ev['phase']} · session {ev['session']} · "
               f"git {ev['git_state']} · last commit: {ev['last_commit']}")
    elif kind == "stream" and stream:
        sys.stderr.write(ev["text"])
        sys.stderr.flush()


def _wants_player(state: dict) -> bool:
    return bool(state.get("awaiting")) or (
        state.get("phase") in _ASK and not state.get("busy")
        and "advance" in state.get("actions", ()))


def _prompt(state: dict) -> str:
    phase, n = state["phase"], state.get("session") or 0
    if not state.get("awaiting"):
        return _ASK[phase].format(n=n, next=n + 1) + " [Y/n] "
    if state["awaiting"] == "confirm":
        return "[Enter confirms · or type a reaction] > "
    return "> "


def _command(client, state: dict, line: str) -> str:
    """Act on one typed line: "quit", "sent" (wait for the engine), or "local"."""
    text = line.strip()
    low = text.lower()
    if low in ("/quit", "/exit", "/q"):
        return "quit"
    if low.startswith("/roll"):
        _print(roll_expr(text[5:].strip()) or "could not parse — try /roll 2d6+3")
        return "local"
    if not state.get("awaiting"):  # a yes/no at a phase boundary
        if low not in ("", "y", "yes"):
            return "quit"
        cmd = {"type": "advance"}
    elif low == "/wrap":
        cmd = {"type": "advance"}
    elif low == "/status":
        cmd = {"type": "status"}
    elif low.startswith("/meta"):
        cmd = {"type": "meta", "text": text[5:].strip()}
    elif text or state["awaiting"] == "confirm":
        cmd = {"type": "input", "text": text}
    else:
        return "local"
    client.send(cmd)
    return "sent"


def run(client, *, stream: bool = False) -> int:
    """Drive the engine behind `client` until the player quits or the engine closes."""
    state: dict = {}
    # Ask only once the engine has answered our last command: a state change, or an
    # `error`/`status` reply that leaves the state as it was.
    fresh = False
    try:
        while True:
            try:
                ev = client.events.get(timeout=0.2)
            except queue.Empty:
                ev = None
            except KeyboardInterrupt:
                if "cancel" in state.get("actions", ()):
                    client.send({"type": "cancel"})
                    continue
                return 130
            if ev is not None:
                if ev["type"] == "state":
                    state, fresh = ev, True
                    if ev["phase"] == "closed":
                        return 0
                else:
                    _render(ev, stream=stream, human=state.get("player") != "auto")
                    fresh = fresh or ev["type"] in ("error", "status")
                continue
            if not (fresh and _wants_player(state)):
                continue
            try:
                line = input(_prompt(state))
            except (EOFError, KeyboardInterrupt):
                _print()
                return 0
            done = _command(client, state, line)
            if done == "quit":
                return 0
            fresh = done == "local"
    finally:
        client.close()
