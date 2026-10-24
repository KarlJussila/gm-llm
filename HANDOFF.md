# Handoff — live play on Luna (2026-10-24)

Ongoing work, kept transferable between agents. The plan is `ROADMAP.md`; the design is
`design/luna.md` and `design/benchmark.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`).

## Where things stand

- **The prompt rework** is tagged `luna-clean-slate` (`18f8d29`). Prose added after the tag is
  trimmed only through `/refine-prompts`; a new guardrail names the failure and the run (campaign
  directory + archive run id).
- **Shakedown has moved to Karl's own campaigns** on Desktop, played through the TUI:
  - `~/Desktop/luna-campaign`: sessions 1–2 played and reconciled, session 3 planned.
  - `~/Desktop/luna-campaign2`: setup, then session 1 planned. Its setup run
    (`20261024T005158Z-c601`) showed the failures fixed in `e00fa1d`.
  - `~/Desktop/luna-campaign3`: session 1 in play under the old planning prompts (run
    `20261024T033752Z-967c`). Its first fifteen minutes drove `7c727f1` through `a13a6e3`.
- **Landed since 2026-10-21, never yet run on Luna:**
  - The primer is written after the character and arcs, and session 1 opens with a verbatim
    prologue (`53029b3`, seam fixed in `7c727f1`).
  - The planning rework (`a13a6e3`). `session-plan` opens with what the session offers the
    character and leaves the everyday world (pay, deals, bystanders) to the runner. The runner
    improvises more freely and checks what it adds against canon.
  - The `author` subagent is now `helper`, a general-purpose subagent, and `author-brief` is now
    `plan-brief` (`a940b0b`).
  - opencode auto-compaction is back on (`65353a2`). Under ChatGPT OAuth, opencode caps OpenAI
    models at 400k context / 272k input.
- **Karl's install** needs `/quit`, `pipx reinstall gm-llm`, `gm-llm update` to pick these up. The
  build is hatchling now (`414e810`), so no `rm -rf build`.

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
  anything that just needs *a* model, such as wiring and tool checks. Never use them for Luna's
  measurements.

## Open, outside the repo

- Karl's global `~/.config/opencode/plugin/task-signal.ts` and `plugins/dice-roller.ts` are v1
  plugins and fail to load under opencode 2.x.
