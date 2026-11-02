# Handoff — autonomous play on Luna (2026-11-02)

Ongoing work, kept transferable between agents. The plan is `ROADMAP.md`; the design is
`design/luna.md` and `design/benchmark.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`).

## Where things stand

- **The prompt rework** is tagged `luna-clean-slate` (`18f8d29`). Prose added after the tag is
  trimmed only through `/refine-prompts`; a new guardrail names the failure and the run (campaign
  directory + archive run id).
- **Shakedown runs as autonomous play** (`play --player auto`, with `--setup-script
  ~/Desktop/dallid-setup.md` for setup). `~/Desktop/luna-campaign6` (run `20261102T032917Z-c936`)
  played two sessions and was stopped. Its plot was dry: an arc of permit disputes with no real
  opposition, which hinged on Dallid changing his ethics unprompted, far from the brief's level
  5–20 heroic story. Its day-count calendar came from a template placeholder.
- **Landed since campaign6, never yet run:**
  - `arc-design` asks for the brief's story: opposition and stakes that grow by the tiers of play,
    a dangerous opposition, its moves among the turning points, a conflict pressing in every
    stretch, and the world's own calendar (`0bb32e6`).
  - Only the final message is surfaced, for every agent with tools; the AI players keep their
    pinned model whatever the campaign's `model` is (`32a5cb5`).
  - No subagents: the dm does its own work (`b4a91c6`).
- **Next:** a fresh Luna campaign from the same setup script, to see the arcs; then comparison runs
  with the DM on `opencode/glm-5.3-flash-free` and on the local Qwen 3.8 Flash Next (polystrata),
  the player staying on Luna. Each gets a fresh campaign, the same setup script, and
  `feedback-dir: feedback` so no guidance carries over. GLM's free tier once refused a fresh
  server, so check it first with `gm-llm dev ping`. The harness isolates opencode's global config,
  so the polystrata provider has to be defined in the campaign's own opencode config.
- **Campaign6's session 1 opening** looked like the auto-player knowing too much. It wasn't a leak:
  its cold-start lead includes the knowledge ledger, which already lists what the PC knew. Giving
  it the primer instead at session 1 is an option, not yet taken.
- **Karl's install** needs `/quit`, `pipx reinstall gm-llm`, `gm-llm update` to pick these up.

## Benchmark

- `bench-out/luna6d` finished playing (26 turns), but `bench check` failed: `play-checker failed
  after 4 retries` (`check2.log`). It has no checks file and no grades. Re-check it before grading.
- **Rubric v3** (`a13a6e3`). The play checker and the rubric add `herding` and `clarity` (both
  ways). `fabrication` counts only additions that conflict with canon or the plan. Clarity scores
  under a new `narration` dimension. v2 grades don't compare with v3 without re-grading.
- `bench-out/luna7/fresh` is an abandoned fresh-setup attempt driven by a scratch client; ignore it.

## The benchmark pipeline as built

`bench run` → `bench check` → `bench grade` → `bench report` (and `bench status` any time).

- `check` writes `checks-<run>.jsonl` beside each archive: one rolling `play-checker` (Luna xhigh)
  session per run, over the run's first commit (the campaign before play).
- `grade` reads it: one rolling `grader` (Sol 6.1 high) session per run, workspace
  `<out>/grade-ws/<run>/` with the start campaign, `after/` (the run dir's HEAD) and
  `transcript.md`. Each finding is confirmed or rejected against `rubric-v3.md`; only confirmed
  ones score. Unchecked runs are skipped and the report flags them.
- `report` shows checker and gate precision, the defaulted rate (checked turns with no
  submission, gate verdicts passed by default) and the stage correction rate.

## Notes

- Free models (`opencode/glm-5.3-flash-free`, `opencode/deepseek-v4.1-flash-free`) are fine for
  anything that just needs *a* model, such as wiring and tool checks. DM runs on them are real
  data about the harness, but they don't stand in for Luna's measurements.

## Open, outside the repo

- Karl's global `~/.config/opencode/plugin/task-signal.ts` and `plugins/dice-roller.ts` are v1
  plugins and fail to load under opencode 2.x.
