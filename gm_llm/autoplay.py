"""
Autoplay — the gated loop driven by the scripted `player` agent instead of a human.

This is one of the two *player* modes (`--player auto`); the other is a human at a
frontend. It is the offline-human test mode: the player agent gets its character packet on
the first turn (plus the story so far, on a resume) and then just plays, so a whole session
runs unattended. `bench run` is this loop plus fixture scaffolding, condition stamping, and
archive emission — the benchmark's harness, not a second implementation.

Resume is the default when a transcript exists: a fresh start would overwrite it, so that
must be the deliberate `--fresh`. A session whose runner already signalled the end is
refused before the server even boots — the next step there is reconcile, not more play.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .console import (banner, fail, note, sessions_dir, show_turn, speaker, warn,
                      with_engine)
from .orchestrator import Game, play_combat
from .orchestrator.canon import latest_session
from .orchestrator.loop import session_is_complete
from .orchestrator.prompts import player_turn


def find_character(directory, override) -> str:
    """Resolve the player packet: `--character` wins ('' = deliberately blind); otherwise
    auto-discover a `*.player.md` at the project root — the convention for campaign-anchored
    packets, kept out of `campaign/` (it's a harness fixture, not canon)."""
    if override is not None:
        return override
    packs = sorted(Path(directory).glob("*.player.md"))
    if packs:
        return str(packs[0])
    warn("no *.player.md at the project root and no --character — player runs blind")
    return ""


def _console_combat(game, backend, player_sid, entry_scene):
    """Print a fight to the console as `play_combat` drives it. The loop — driver pumping,
    PC-slot prompting, turn accounting — is the library's; this is only the console dialect
    of its three hooks. No cap: autoplay caps normal turns only, so `hit_cap` can't fire.
    Returns the exit narration, which the caller resumes normal play from."""
    def on_beat(narration, who):
        speaker(f"COMBAT · {who}", "1;35", narration)
        return None  # autoplay never interjects

    scene, _turns, _hit_cap = play_combat(
        game, backend, player_sid, entry_scene,
        on_beat=on_beat,
        on_slot=lambda ev, _t: note(f"combat: PC slot (round {ev.round}) — "
                                    f"waiting on the player…"),
        on_player=lambda text: speaker("PLAYER · combat", "1;32", text))
    speaker("DM · combat ends", "1;36", scene)
    return scene


def run(args) -> None:
    """The console autoplay command. Exits via `with_engine`."""
    n = latest_session(sessions_dir(args.dir))
    if n and not args.fresh and session_is_complete(args.dir, n):
        fail(f"session {n} is already complete (task_complete fired) — run "
             f"`python -m gm_llm dev reconcile` to fold it into canon, or --fresh to replay it")
        sys.exit(2)

    character, char_path = "", find_character(args.dir, args.character)
    if char_path and os.path.exists(char_path):
        character = re.sub(r"<!--.*?-->", "", Path(char_path).read_text(encoding="utf-8"),
                           flags=re.DOTALL).strip()
        note(f"player packet: {char_path} ({len(character)} chars)")
    elif char_path:
        warn(f"WARNING: no character packet at {char_path} — player runs blind")

    def intro(story, scene):
        """The first turn's extras (packet, story-so-far) in front of the per-turn message;
        every turn ends in the same player_turn() reminder + <dm> fence."""
        parts = []
        if character:
            parts.append("[YOUR CHARACTER — read this, then stay in character for the rest "
                         f"of the session]\n\n{character}")
        if story is not None:
            parts.append(f"[This session is already underway. The story so far:]\n\n{story}")
        parts.append(player_turn(scene))
        return "\n\n".join(parts)

    def body(backend, gate, logs):
        game = Game(backend, gate, logs=logs)
        player_sid = backend.create_session("play-player")
        note(f"runner={game.runner_sid} player={player_sid} session={game.session}")

        scene, story = None, None
        if not args.fresh:
            note("resuming if a transcript exists (a rebuild is one model call — "
                 "silent up to the timeout if rate-limited)…")
            scene = game.resume()  # None if there's no transcript to pick up
            if scene is not None:
                story = game._read_transcript()
                note(f"resumed session {game.session} from its transcript "
                     f"(--fresh restarts instead).")
                speaker("DM", "1;36", scene)
        if scene is None:
            note("opening the scene — first model call…")
            tr = game.start(args.kickoff)
            scene = tr.final
            speaker("DM", "1;36", scene)
            show_turn(tr)

        for i in range(1, args.turn_cap + 1):
            msg = intro(story, scene) if i == 1 else player_turn(scene)
            story = None  # only the first turn carries the story
            note(f"turn {i}: waiting on the player…")
            player = backend.prompt(player_sid, "player", msg)
            speaker(f"PLAYER · turn {i}", "1;32", player)

            note(f"turn {i}: waiting on the DM (draft + gate)…")
            tr = game.turn(player)
            scene = tr.final
            speaker("DM", "1;36", scene)
            show_turn(tr)
            if tr.combat_started:
                note(f"turn {i}: combat — initiative takes over…")
                scene = _console_combat(game, backend, player_sid, scene)
                continue
            if tr.session_complete:
                banner(f"session {game.session} ended by the runner (turn {i})")
                note("capturing handoff notes from the warm runner session…")
                notes_path = game.handoff()
                note(f"handoff notes: {notes_path}" if notes_path
                     else "no handoff notes captured (optional — reconcile proceeds without them)")
                note("next: `python -m gm_llm dev reconcile` to fold the session into canon")
                break
        else:
            note(f"turn cap ({args.turn_cap}) reached — session still open; "
                 f"re-running autoplay will resume it")

    with_engine(args, body)
