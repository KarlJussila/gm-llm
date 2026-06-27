#!/usr/bin/env python3
"""
Autoplay harness — watch the runner run a session without playing it yourself.

Boots a headless `opencode serve` (which loads the project plugins, so the
check_turn gate and transcript capture all fire normally), then ping-pongs two
sessions: a `player` agent and the `dm-runner`. Each exchange is streamed to the
console, and after every DM turn the new check verdicts (written by the turn-gate
plugin to /tmp/turn-gate-checks.log) are echoed inline — so you see narration,
checks, and the player's reply in one stream.

    python3 .opencode/dev/autoplay.py --turns 12

Nothing here is part of the engine; it's a dev rig. Ctrl-C stops it and shuts the
server down.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CHECKS_LOG = "/tmp/turn-gate-checks.log"
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])  # .opencode/dev -> repo root


def post(base, path, directory, body, timeout):
    url = f"{base}{path}?directory={urllib.parse.quote(directory)}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_for_server(base, directory, deadline):
    """Block until the server answers a session-create, returning the new id."""
    last = None
    while time.time() < deadline:
        try:
            return post(base, "/session", directory, {}, timeout=10)["id"]
        except (urllib.error.URLError, ConnectionError, OSError, KeyError) as e:
            last = e
            time.sleep(0.5)
    raise RuntimeError(f"server never came up: {last}")


def last_text(resp):
    parts = resp.get("parts", []) if isinstance(resp, dict) else []
    texts = [p.get("text", "") for p in parts if p.get("type") == "text" and p.get("text")]
    return texts[-1].strip() if texts else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=10, help="player/DM exchanges to run")
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--dir", default=PROJECT_ROOT, help="campaign project dir")
    ap.add_argument("--kickoff", default="Let's begin the session.", help="first message to the DM")
    ap.add_argument("--turn-timeout", type=int, default=900, help="seconds to wait per model turn")
    ap.add_argument("--character", default=str(Path(__file__).resolve().parent / "dallid.player.md"),
                    help="player packet injected into the player's first message ('' to skip)")
    args = ap.parse_args()
    directory = str(Path(args.dir).resolve())
    base = f"http://127.0.0.1:{args.port}"

    character = ""
    if args.character and os.path.exists(args.character):
        character = Path(args.character).read_text()
        print(f"[harness] player packet: {args.character} ({len(character)} chars)", flush=True)
    elif args.character:
        print(f"[harness] WARNING: no character packet at {args.character} — player runs blind", flush=True)

    # Only show check verdicts written from this run forward.
    checks_offset = os.path.getsize(CHECKS_LOG) if os.path.exists(CHECKS_LOG) else 0

    def echo_new_checks():
        nonlocal checks_offset
        if not os.path.exists(CHECKS_LOG):
            return
        with open(CHECKS_LOG, "r", errors="replace") as f:
            f.seek(checks_offset)
            new = f.read()
            checks_offset = f.tell()
        if new.strip():
            print(new, end="", flush=True)

    print(f"[harness] starting opencode serve on :{args.port} (dir={directory})", flush=True)
    serve_log = open("/tmp/autoplay-serve.log", "w")
    serve = subprocess.Popen(
        ["opencode", "serve", "--port", str(args.port)],
        cwd=directory, stdout=serve_log, stderr=subprocess.STDOUT,
    )

    def shutdown(*_):
        print("\n[harness] shutting down…", flush=True)
        try:
            serve.send_signal(signal.SIGINT)
            serve.wait(timeout=10)
        except Exception:
            serve.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    try:
        runner_sid = wait_for_server(base, directory, deadline=time.time() + 60)
        player_sid = post(base, "/session", directory, {"title": "autoplay-player"}, timeout=10)["id"]
        print(f"[harness] runner={runner_sid} player={player_sid}\n", flush=True)

        def ask(sid, agent, text):
            resp = post(base, f"/session/{sid}/message", directory,
                        {"agent": agent, "parts": [{"type": "text", "text": text}]},
                        timeout=args.turn_timeout)
            return last_text(resp)

        # Kick off: the DM opens the scene.
        dm = ask(runner_sid, "dm-runner", args.kickoff)
        print(f"━━ DM ━━\n{dm}\n", flush=True)
        echo_new_checks()

        for i in range(1, args.turns + 1):
            # Establish the character on turn 1 by prepending the packet to the
            # first thing the player sees; it persists in the player's session.
            if i == 1 and character:
                msg = (f"[YOUR CHARACTER — read this, then stay in character for the rest of the session]\n\n"
                       f"{character}\n\n[The session begins. The DM says:]\n\n{dm}")
            else:
                msg = dm
            player = ask(player_sid, "player", msg)
            print(f"━━ PLAYER (turn {i}) ━━\n{player}\n", flush=True)

            dm = ask(runner_sid, "dm-runner", player)
            print(f"━━ DM ━━\n{dm}\n", flush=True)
            echo_new_checks()

        print("[harness] done.", flush=True)
    finally:
        shutdown()


if __name__ == "__main__":
    main()
