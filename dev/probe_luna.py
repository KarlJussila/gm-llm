#!/usr/bin/env python3
"""
Diagnostic live-play probe for Luna Tier 1 (ROADMAP luna #1).

Runs Hollowfell session 3 with `openai/gpt-5.6-luna-fast` at `xhigh` reasoning:
  - minimal live-DM role, spoiler boundary, and file/tool layout
  - no per-turn reminder, todo choreography, forced skill loading, or wrap countdown
  - observe-only checking: narrative-checker evaluates drafts, but verdicts are NOT
    fed back to Luna (final == draft; no correction passes)
  - drives play through the scripted `player` agent (Dallid)
  - captures transcript, raw archive, tool calls, context usage, and gate reports.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gm_llm.orchestrator import (
    AgentPlayer, Backend, BackendError, CanonPreloader, Game, Gate, Logs,
    PlayHooks, TurnResult, play_session,
)
from gm_llm.project import init_project, install_plugin_deps

LUNA_AGENT_MD = """---
description: >-
  Runs one live D&D session as the Dungeon Master — narrating scenes, roleplaying NPCs,
  adjudicating player actions, and calling for or rolling dice.
mode: primary
model: openai/gpt-5.6-luna-fast
variant: xhigh
permission:
  '*': deny
  read: allow
  glob: allow
  grep: allow
  list: allow
  dice: allow
  task_complete: allow
  start_encounter: allow
  end_encounter: allow
  damage: allow
  heal: allow
  add_condition: allow
  remove_condition: allow
  move: allow
  set_dead: allow
  death_save: allow
  use_reaction: allow
  remind_in: allow
  remind_each_turn: allow
  clear_timer: allow
  advance_turn: allow
  state: allow
  describe: allow
  distance_between: allow
  burst: allow
  cone: allow
  line: allow
---

You are the Dungeon Master running a live D&D 5e session for a solo player. You narrate the world, roleplay NPCs, adjudicate player actions, and call for or make rolls.

## Rules & Role
- **Drive the story from the plan:** Adjudicate the current scene and guide the narrative through the prepared session plan.
- **Narrate what happens, never the player's choices:** The player controls their own character. You describe the environment, the consequences of their actions, NPC dialogue, and sensory details. Never decide what the character thinks, feels, or chooses to do.
- **Spoiler boundary:** Keep all secret lore, unrevealed plot threads, and upcoming encounter details strictly hidden until the player legitimately discovers them through play.

## Campaign Structure
The campaign files live on disk if you need to reference them:
- `campaign/world/` — locations, factions, and world lore.
- `campaign/characters/` — NPC profiles, allegiances, and notes.
- `campaign/sessions/` — session plans, previous session digests, and transcripts.
Use `read`, `grep`, or `glob` if you need to check a specific detail from canon.

## Tools
- **`dice`**: Use to roll dice for NPCs, environmental events, or contested checks. When the player needs to make an ability check, saving throw, or attack roll, state the check and DC clearly in your narration and wait for them to roll.
- **`task_complete`**: When the session reaches a natural narrative conclusion (the objectives are fulfilled or the party rests/wraps), call `task_complete(notes="...")` as your final action. In `notes`, summarize the session's key events, discoveries, NPC state changes, and unresolved threads for the next session.
- **Combat**: If combat breaks out, use `start_encounter` to begin initiative tracking, adjudicate combat rounds using the combat tools, and call `end_encounter` when the fight concludes.
"""


class ProbeGame(Game):
    """A clean live-play Game without Tier-0 control machinery:
    - No per-turn reminder brief
    - No todo list choreography
    - No staleness count escalation
    - No wrap countdown banner
    - Observe-only gate checking (draft is never corrected; final == draft)
    """

    def __init__(self, backend: Backend, gate: Gate, logs: Logs | None = None, session: int = 3):
        super().__init__(backend, gate, runner_agent="luna-dm", logs=logs, session=session)

    def turn(self, player_input: str) -> TurnResult:
        # Minimal delivery: clean player message without reminder, staleness, or wrap nags
        message = f"<player>\n{player_input}\n</player>"
        return self._gated_turn(message, player_input)

    def _run_gate(self, draft: str, player_msg: str, in_combat: bool = False):
        # Observe-only: run the independent checks for measurement, but NEVER steer Luna
        self._step("check")
        result = self.gate.check(draft, player_msg, in_combat=in_combat)
        return draft, result, False

    def _gated_turn(self, message: str, player_msg: str, opening: bool = False) -> TurnResult:
        self._correcting = False
        self._turn_no += 1
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, message)
        draft = reply.text
        # Check if Luna called task_complete cleanly on its own (no nudge)
        session_complete = (not opening) and ("task_complete" in reply.tools)
        if session_complete:
            self._mark_complete()
        final, result, corrected = self._run_gate(draft, player_msg)
        self._step("done")
        self._combat_observe(reply)
        self._observe_consult(reply)
        tr = TurnResult(
            player_msg, draft, final, result, corrected, session_complete,
            combat_started=("start_encounter" in reply.tools),
            close_nudged=False, tools=frozenset(reply.tools),
        )
        self._append_transcript(player_msg, final, opening)
        cu = self.backend.context_usage(self.runner_sid)
        self._update_wrap_countdown(session_complete, cu)
        self._log(tr)
        self._archive_turn(tr, opening, cu)
        if self.on_turn:
            self.on_turn(tr)
        return tr


def prepare_run_dir(run_dir: Path) -> None:
    if run_dir.exists():
        print(f"[probe] clearing existing {run_dir}…")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[probe] initializing project assets into {run_dir}…")
    init_project(run_dir)

    # Reuse node_modules from bench template if present, or install
    template_modules = ROOT / "bench-out" / "template" / ".opencode" / "node_modules"
    target_modules = run_dir / ".opencode" / "node_modules"
    if template_modules.is_dir():
        print("[probe] copying node_modules from bench template…")
        shutil.copytree(template_modules, target_modules)
    else:
        print("[probe] installing plugin dependencies…")
        ok, msg = install_plugin_deps(run_dir / ".opencode")
        if not ok:
            print(f"[probe] WARNING: plugin install failed: {msg}")

    # Write luna-dm agent
    agent_path = run_dir / ".opencode" / "agent" / "luna-dm.md"
    agent_path.write_text(LUNA_AGENT_MD, encoding="utf-8")
    print(f"[probe] wrote {agent_path}")

    # Copy Hollowfell fixture campaign
    fixture_campaign = ROOT / "dev" / "fixtures" / "hollowfell" / "campaign"
    target_campaign = run_dir / "campaign"
    print(f"[probe] copying fixture from {fixture_campaign}…")
    shutil.copytree(fixture_campaign, target_campaign)

    # Git init and initial commit
    print("[probe] initializing git repository…")
    subprocess.run(["git", "init", "-q"], cwd=run_dir, check=True)
    (run_dir / ".gitignore").write_text(".opencode/\n", encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "gm-llm probe"], cwd=run_dir, check=True)
    subprocess.run(["git", "config", "user.email", "probe@local"], cwd=run_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=run_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial hollowfell fixture"], cwd=run_dir, check=True)


def main():
    run_dir = ROOT / "bench-out" / "probe-luna-1"
    prepare_run_dir(run_dir)

    logs = Logs.under(project=run_dir, debug=False)
    backend = Backend(str(run_dir), logs=logs, port=4185, min_call_gap=1.0)

    print("\n[probe] booting backend on port 4185…")
    backend.start()

    turn_records: list[dict] = []

    def on_prompt(t: int):
        print(f"\n--- Turn {t}: waiting on player ---")

    def on_player(text: str, t: int):
        print(f"[PLAYER] {text.strip()}")

    def on_turn(tr: TurnResult):
        print(f"[DM - LUNA] {tr.final.strip()[:200]}… (len={len(tr.final)})")
        if tr.tools:
            print(f"  [tools called] {sorted(tr.tools)}")
        g = tr.gate
        v_turn = "PASS" if g.narrative.passed else f"FAIL ({len(g.narrative.report.splitlines())} lines)"
        v_cond = "PASS" if g.conduct.passed else f"FAIL ({len(g.conduct.report.splitlines())} lines)"
        print(f"  [gate observe] check-turn: {v_turn} | check-conduct: {v_cond}")
        if not g.narrative.passed:
            print(f"    check-turn report: {g.narrative.report.strip()[:300]}")
        if not g.conduct.passed:
            print(f"    check-conduct report: {g.conduct.report.strip()[:300]}")
        if tr.session_complete:
            print("  *** TASK COMPLETE SIGNALLED BY LUNA ***")
        cu = backend.context_usage(game.runner_sid)
        if cu:
            print(f"  [context] tokens: {cu.tokens} / limit: {cu.context_limit}")
        turn_records.append({
            "turn": tr._turn_no if hasattr(tr, "_turn_no") else len(turn_records) + 1,
            "player": tr.player_input,
            "final": tr.final,
            "tools": list(tr.tools),
            "check_turn_passed": g.narrative.passed,
            "check_turn_report": g.narrative.report,
            "check_conduct_passed": g.conduct.passed,
            "check_conduct_report": g.conduct.report,
            "session_complete": tr.session_complete,
            "tokens": cu.tokens if cu else None,
        })

    hooks = PlayHooks(
        on_prompt=on_prompt,
        on_player=on_player,
        on_turn=on_turn,
    )

    try:
        preloader = CanonPreloader(run_dir / "campaign")
        gate = Gate(backend, preloader, logs=logs)
        game = ProbeGame(backend, gate, logs=logs, session=3)

        # Autoplayer packet
        packet_path = run_dir / "campaign" / "documents" / "dallid.player.md"
        packet = re.sub(r"<!--.*?-->", "", packet_path.read_text(encoding="utf-8"), flags=re.DOTALL).strip()
        player_sid = backend.create_session("probe-player")
        player_source = AgentPlayer(backend, player_sid, character=packet)

        print("\n[probe] starting session (opening scene)…")
        start_time = time.time()
        opening = game.start("Let's begin the session.")
        print(f"[DM - LUNA OPENING]\n{opening.final.strip()}\n")

        print("[probe] entering session loop (turn cap: 35)…")
        result = play_session(game, player_source, opening.final, hooks=hooks, turn_cap=35)
        duration = time.time() - start_time

        print("\n========================================================")
        print(f"[probe] SESSION ENDED: outcome={result.outcome} in {result.turns} turns ({duration:.1f}s)")
        print("========================================================")

        # Print detailed telemetry summary
        complete_called = any(r["session_complete"] for r in turn_records)
        all_tools = [t for r in turn_records for t in r["tools"]]
        check_turn_violations = [r for r in turn_records if not r["check_turn_passed"]]
        check_conduct_violations = [r for r in turn_records if not r["check_conduct_passed"]]

        print(f"\n[SUMMARY]")
        print(f"Total turns: {result.turns}")
        print(f"Natural close (task_complete): {complete_called}")
        print(f"Tools used: {all_tools}")
        print(f"check-turn violations: {len(check_turn_violations)} turns")
        print(f"check-conduct violations: {len(check_conduct_violations)} turns")
        if turn_records:
            t_first = turn_records[0]["tokens"]
            t_last = turn_records[-1]["tokens"]
            print(f"Context growth: {t_first} tokens -> {t_last} tokens")

        transcript_path = run_dir / "campaign" / "sessions" / "session-3-transcript.md"
        if transcript_path.is_file():
            print(f"\nTranscript saved at: {transcript_path} ({transcript_path.stat().st_size} bytes)")

    finally:
        print("\n[probe] stopping backend…")
        backend.stop()


if __name__ == "__main__":
    main()
