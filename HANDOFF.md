# Handoff — luna task 2 in progress (2026-10-20)

Temporary: delete this file once task 2 lands. The plan is `ROADMAP.md`; the design is
`design/luna.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`).

## Done

- **luna 1 — layout v2** (commit `1974a4b`): generated INDEX, frontmatter vitals, secret ids with
  `[learned:<id> S<n>]` reveals, `sessions/<n>/` folders, the canon lint (`orchestrator/lint.py`,
  `registry.py`, `reveals.py`, `paths.py`), templates and `canon-conventions` rewritten, Hollowfell
  converted (its feedback files now sit at `dev/fixtures/hollowfell/feedback/`).
- **luna 2 — code, mostly done** (this WIP commit):
  - `loop.py` rewritten: the message is `<player>…</player>` only; no reminder, staleness, wrap
    countdown or in-loop gate; `Game(backend, preloader, …)` (Lifecycle passes `gate.preloader`);
    `TurnResult(player_input, final, session_complete, combat_started, close_nudged, tools)`; the
    closing `task_complete` carries `player_message` (joined into the transcript) and `notes`
    (filed to `sessions/<n>/notes.md`); `handoff()` only asks when notes are missing.
  - `combat.py`: no `combat-reminder` resend, no gate; every beat archived as a `turn` event with
    `combat: {combatant, before, after}` tracker frames.
  - Console, TUI (`_render_turn_detail`), mock and tests updated; `dev/probe_luna.py` deleted.
  - Prompts: new `agent/dm-runner.md` (Luna `xhigh`; table rules, plan use and pacing in the
    prompt); `session-run` and `session-flow` deleted; `session-close` rewritten (one closing
    `task_complete` with `player_message` + `notes`, and what the notes cover); `combat-run`,
    `social-play`, `discoveries` descriptions say when to load, `session-run` references removed.

## Still to do for task 2

1. **`dev/test_golden_stream.py` is red** — the only failing test. Its scripted fake backend still
   expects narrative-checker replies during play and asserts `.corrected`. Remove the in-play
   checker replies and correction turn from its script, update the assertions, then re-record with
   `UPDATE_GOLDEN=1`.
2. Delete the now-unused briefs: `prompts/turn-reminder.md`, `turn-refresh.md`, `session-length.md`,
   `combat-reminder.md`, `correct-turn.md`; rewrite `runner-header.md` to one plain sentence
   ("your prepared context — the plan is yours alone; everything else is on disk under
   campaign/") and update `handoff-brief.md` to point at `session-close`'s notes list.
3. Pin every other agent to `model: openai/gpt-6-luna` + `variant: xhigh`, dropping `temperature`
   (`dm`, `log-extractor`, `campaign-analyst`, `narrative-checker`, `player`).
4. `plugin/task-complete.ts`: make the `notes` description task-agnostic ("closing notes for the
   task — only when the task asks for them").
5. `combat-run` has a leftover "confirm gate" section that partly repeats the new "How a fight runs"
   section — trim it. Check `combat-balance`'s description says when to load.
6. Commit, then go on to luna 3 (reconcile and planning).

## Live testing

Luna quota was due back about 30 minutes after this session started. Once task 2 is done, luna 6
(a Hollowfell play run) can start before 3–5 if you want early evidence: `bench run` against
`dev/fixtures/hollowfell` with `--play-only`.
