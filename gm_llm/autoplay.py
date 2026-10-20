"""
Autoplay — the gated loop driven by the scripted `player` agent instead of a human.

This is one of the two *player* modes (`--player auto`); the other is a human at a
frontend. It is the offline-human test mode: the player agent gets its character packet on
the first turn (plus the story so far, on a resume) and then just plays, so a whole session
runs unattended. `bench run` is this loop plus fixture scaffolding, condition stamping, and
archive emission — the benchmark's harness, not a second implementation.

Neither is *this* the loop: since frontends 2 the loop is `orchestrator.play_session`, and
what lives here is the console dialect of it — an `AgentPlayer` for the player end and a set
of `PlayHooks` for the output — plus the session opening and the post-wrap tail, which are
per-mode. Watching the same player agent in the TUI is the same source under different hooks
(`gm-llm play --player auto --ui tui`).

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
from .orchestrator import AgentPlayer, Game, PlayHooks, play_session
from .orchestrator.paths import latest_session
from .orchestrator.loop import session_is_complete


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


def read_character(directory, override) -> str:
    """The packet's text, comments stripped — what an `AgentPlayer` primes its first message
    with. Shared by the console mode and `--player auto --ui tui`, which resolve the packet
    the same way (`bench run` reads its own from `fixture.json`; one canonical contract for
    all three is benchmark B1's, still open)."""
    char_path = find_character(directory, override)
    if char_path and os.path.exists(char_path):
        text = re.sub(r"<!--.*?-->", "", Path(char_path).read_text(encoding="utf-8"),
                      flags=re.DOTALL).strip()
        note(f"player packet: {char_path} ({len(text)} chars)")
        return text
    if char_path:
        warn(f"WARNING: no character packet at {char_path} — player runs blind")
    return ""


def _hooks() -> PlayHooks:
    """The console dialect of the session loop's events. No `on_interrupt`: an unattended
    run has nobody to hand a failed call back to, so a give-up rides out to `with_engine`.
    `on_beat` renders and never interjects — it returns None (the confirm channel), so every
    NPC beat is auto-confirmed."""
    def turn(tr):
        speaker("DM", "1;36", tr.final)
        show_turn(tr)
        if tr.combat_started:
            note("combat — initiative takes over…")

    return PlayHooks(
        on_prompt=lambda t: note(f"turn {t}: waiting on the player…"),
        on_player=lambda text, t: (speaker(f"PLAYER · turn {t}", "1;32", text),
                                   note(f"turn {t}: waiting on the DM (draft + gate)…")),
        on_turn=turn,
        on_slot=lambda ev, t: note(f"turn {t}: combat — PC slot (round {ev.round}), "
                                   f"waiting on the player…"),
        on_beat=lambda narration, who: speaker(f"COMBAT · {who}", "1;35", narration),
        on_combat_end=lambda narration: speaker("DM · combat ends", "1;36", narration),
    )


def run(args) -> None:
    """The console autoplay command. Exits via `with_engine`."""
    n = latest_session(Path(args.dir) / "campaign")
    if n and not args.fresh and session_is_complete(args.dir, n):
        fail(f"session {n} is already complete (task_complete fired) — run "
             f"`python -m gm_llm dev reconcile` to fold it into canon, or --fresh to replay it")
        sys.exit(2)

    character = read_character(args.dir, args.character)

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

        # The cap covers combat slots too (`play_session`), which console autoplay used not
        # to do: an endless fight is exactly the case a safety net is for.
        source = AgentPlayer(backend, player_sid, character=character, story=story)
        result = play_session(game, source, scene, hooks=_hooks(), turn_cap=args.turn_cap)

        if result.outcome == "cap":
            note(f"turn cap ({args.turn_cap}) reached — session still open; "
                 f"re-running autoplay will resume it")
            return
        banner(f"session {game.session} ended by the runner (turn {result.turns})")
        note("capturing handoff notes from the warm runner session…")
        notes_path = game.handoff()
        note(f"handoff notes: {notes_path}" if notes_path
             else "no handoff notes captured (optional — reconcile proceeds without them)")
        note("next: `python -m gm_llm dev reconcile` to fold the session into canon")

    with_engine(args, body)
