# Handoff — after the Luna prompt rework (2026-10-21)

Temporary: delete this file once luna 6 lands. The plan is `ROADMAP.md`; the design is
`design/luna.md` and `design/benchmark.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`).

## Where things stand

- **The prompt rework is complete** and tagged `luna-clean-slate` (`18f8d29`). Prose added after
  the tag is trimmed only through `/refine-prompts`; a new guardrail names the failure and the run.
- **Everything that needed no model quota has landed:** frontends 1 (`9db2c00`), B5 conditions and
  tiers (`8fabf13`), `bench status` (`d398bbf`), B7 the after-play checker (`5718709`), B8 the
  grader rework (`bebefa4`, `59f1914`). The suite is green.
- **What's left needs quota or Karl:** luna 6 (live shakedown), 7 (between-session and combat
  shakedown), 8 (release); then B3 (`low` baseline), B9, B10. Packaging 1 needs a Windows box.

## luna 6 in progress

- `bench-out/luna6b/run-20261021T125839Z-fd89` played session 3 (28 turns, natural close) and
  reconciled through propagation; the OpenAI usage limit hit during session 4's prep. Finish it
  with `python -m gm_llm bench run --out bench-out/luna6b --resume`, then `bench check` and
  `bench grade` on it (their first real-model run), then play session 4.
- Fixed from the runs: the dice tool's DM-directed reminder (`8541c1b`); `discoveries` now says a
  check reveals details and conclusions only through them (`3eb602c`, `c8d2e6b`, Karl's wording);
  reconcile counts as done only once the next plan is archived (`a0a2f5f`).
- Watched, once each: the DM rolled a PC check itself, then discarded it and asked (s3t4).
- `bench-out/luna6` is the aborted first attempt (the dice bug); ignore it.

## The benchmark pipeline as built

`bench run` → `bench check` → `bench grade` → `bench report` (and `bench status` any time).

- `check` writes `checks-<run>.jsonl` beside each archive: one rolling `play-checker` (Luna xhigh)
  session per run, over the run's first commit (the campaign before play).
- `grade` reads it: one rolling `grader` (Sol 6.1 high) session per run, workspace
  `<out>/grade-ws/<run>/` with the start campaign, `after/` (the run dir's HEAD) and
  `transcript.md`. Each finding is confirmed or rejected against `rubric-v2.md`; only confirmed
  ones score. Unchecked runs are skipped and the report flags them.
- `report` shows checker and gate precision, the defaulted rate (checked turns with no
  submission, gate verdicts passed by default) and the stage correction rate.

## Never run against a real model

- The autoplayer (`player.md`, `player-rolls`, `player-combat`), a whole `bench run`, and
  `autoplay.run` end to end.
- The `submit_checks` and `submit_grade` plugin tools. The `play-checker` and `grader` agents
  load in `opencode serve` with the right model, variant and permissions (probed); the tools
  registering and being called is unverified.
- `opencode serve` loads a plain directory's `.opencode/` agents; only `opencode debug agents`
  wanted a git repo (so the check and grade workspaces aren't repos).

## For Karl

- Review the prompt-rework commits — the `refine-prompts` "approve the first few" step was skipped
  while you were away: `e961feb`, `035459f`, `c5e8073`, `38768b3`, `6d3cd2f`, `e2a20f1`, `54f1203`.
- Review `dev/fixtures/hollowfell/story.md`, the story-so-far recap Claude wrote from the S1–S2
  transcripts (it leaves out the Concordance records slip on purpose).
- Token usage for `check-ws` isn't counted by `gm-llm tokens` (only `run-*` and `grade-ws`).

## Open, outside the repo

- Karl's global `~/.config/opencode/plugin/task-signal.ts` and `plugins/dice-roller.ts` are v1
  plugins and fail to load under opencode 2.x.
