# Changelog

All notable changes to gm-llm are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project uses `0.x` versioning
(minor = a feature set or new mode, patch = fixes and small changes — see `CLAUDE.md`).

There is no PyPI publish: a "release" is the version-bump commit, which live campaigns pick up via
`pipx reinstall` + `gm-llm update`. The single source of the version is `gm_llm/__init__.py`.

## [Unreleased]

### Added
- **Per-turn player reminder** — the autoplayer now gets a fresh `player-reminder` brief in front
  of every DM beat (the beat fenced in `<dm>…</dm>`), mirroring the runner's `turn-reminder`: a
  per-turn algorithm (roll handling, one action, no recap/repetition, attempt-never-resolve, no
  invented facts). One home (`orchestrator/prompts/player-reminder.md` + `prompts.player_turn`),
  used by both `dev/cli.py play` and the bench runner. Counters the observed long-session drift:
  echo spirals, world-narration, and perception loops.
### Changed
- `dev/cli.py play` needs no hand-holding: it auto-resumes an in-progress session (`--fresh` is
  now the only way to overwrite a transcript), auto-discovers a `*.player.md` packet at the
  project root, stops when the runner ends the session (capturing the handoff notes and pointing
  at reconcile), refuses to play a session already marked complete, and treats `--turns`
  (default 30, up from 6) as a cap rather than a fixed count.

## [0.4.0] — 2026-07-17

Benchmark harness — gm-llm doubles as a tiered scaffolding benchmark (design in `BENCHMARK.md`):
fixture runner, grader, report, and golden-stream regression armor (B1/B2/B4).

### Added
- `CHANGELOG.md` (this file).
- **Benchmark runner (B1)** — `bench run` (dev-only, under `gm_llm/bench/`, wheel-excluded like
  `dev/`): plays a frozen fixture campaign through the product's gated loop N times and leaves one
  condition-stamped score archive per run. Each run assembles a throwaway project (template +
  fixture `campaign/` + fresh git repo), emits a `conditions` archive event (fixture id/frozen,
  tier, turn cap, reconcile flag, per-agent model+temperature) ahead of play, runs to a natural
  `task_complete` close or a hard turn cap (cap breaches stamped and skipped past reconcile), and
  records outcomes to `<out>/batch.jsonl`. Batches are rate-limit-resilient (a failed run is
  recorded and the batch continues) and resumable (re-invoking the same `--out` appends).
- **Provisional fixture** `dev/fixtures/hollowfell/` — a frozen `init + session-1 plan` campaign
  (world, canon, the `dallid` PC) with a `fixture.json` condition stamp. Marked provisional: it is
  re-frozen from steady-state canon before the B3 baseline.
- `dev/test_bench.py` — standalone checks for run-dir assembly, the conditions event, natural close,
  cap breach, and batch resilience (all over fakes; no network/npm/opencode).
- **Benchmark grader + report (B2)** — `bench grade` and `bench report` (dev-only, under
  `gm_llm/bench/`). `bench grade` scores every violation the in-loop checker flagged in a batch's
  archives: it assembles a minimal throwaway grading workspace (`<out>/grade-ws/` — the pinned
  `grader` agent + a bench-only `submit_grade` plugin), boots one backend over it, and grades each
  finding in its own session against the versioned severity/category rubric (`rubric-v1.md`,
  embedded verbatim in each brief). Grades are delivered as structured `submit_grade` tool calls —
  never parsed from prose; a grader that won't call the tool after one nudge is recorded `ungraded`.
  Output is `grades-<run_id>-v1.jsonl` beside each archive (header + one line per finding: severity,
  category, rationale, `duplicate_of`), idempotent per rubric+model unless `--force`. `--model`
  overrides the pinned grader for a V2 re-grade (grades are derived data); a short window of
  already-graded findings rides in each brief so a violation persisting across consecutive turns is
  marked `duplicate_of` and doesn't multiply the score; `--double [--sample N]` re-grades a sample in
  independent sessions and reports severity/category agreement. `bench report` (no model calls)
  aggregates archives + grades into a per-run and per-batch summary — violation counts by severity
  (raw + dedup'd), correction rate, the prominent defaulted-verdict rate, ungraded count,
  turns-to-wrap, session-close outcomes, stage gates, context growth — as distributions
  (min/median/max), and flags a batch that mixes conditions loudly at the top. `--json` for machine
  output. Grader assets live under `gm_llm/bench/assets/` (instrument, not product — never shipped in
  the wheel).
- `dev/test_grade.py` — standalone checks for brief construction, finding extraction, the grades-file
  shape + idempotence, the ungraded-after-nudge path, dedup via `duplicate_of`, `--double` agreement
  math, and report aggregation incl. the mixed-conditions warning (all over a fake grader backend;
  no network/npm/opencode).
- **Golden prompt-stream test (B4)** — `dev/test_golden_stream.py` + `dev/golden/stream.jsonl`:
  records the exact model-facing prompt stream (one `{seq, agent, kind, message}` record per
  backend call) the orchestrator emits for a scripted setup → session-1 prep → play → handoff →
  reconcile pass, and diffs future streams against it byte-for-byte. Drives the real
  Setup/Planner/Game/Reconciler + real Gate + real CanonPreloader over a synthetic on-disk campaign
  and a scripted-by-agent fake backend (so the checker-bound briefs — canon excerpts, correction
  passes, `task_complete`/`report_findings` handling — are all in the recorded surface). Free
  regression armor for the B5 playbook refactor. `UPDATE_GOLDEN=1 python dev/test_golden_stream.py`
  re-records.

### Changed
- Version is single-sourced from `gm_llm/__init__.py` `__version__`; `pyproject.toml` reads it
  dynamically, so the CLI, `gm-llm update`, and package metadata can no longer drift.

## [0.3.0] — 2026-07-17

Combat play mode — a full tracker-backed combat system (design in `COMBAT.md`).

### Added
- **Combat tracker** — a file-backed opencode plugin over a pure engine: HP, egocentric positions
  (world-Cartesian storage, Chebyshev projection), the bounded condition library, initiative, the
  one-reaction economy, the `dead` bit + death saves, and the turn-slot timer/obligation channel.
  Holds `committed`/`pending` frames with forward mutators + `rollback`.
- **Initiative-driven mode switch** — the orchestrator drives combat turn by turn with granular
  commit / confirm / interject, plus resume-mid-combat recovery (rollback + re-resolve).
- **`check-combat`** — a narrative-checker role validating the `committed → pending` mechanical delta.
- **Repertoire ledger** — the PC's `{slug}.repertoire.md`, a third ledger of reaction triggers with a
  player-owned `Stop:` toggle, seeded at create/level-up and grown from play.
- **Planning layer** — a stat-block template, a `world/bestiary/` reusable-creature file kind
  (registered in a new INDEX `Bestiary` table), and the `combat-balance` skill (solo-game difficulty
  by feel).
- **Play-craft** — the `combat-run` skill and the `combat-reminder` per-turn brief.
- **AoE queries** — `burst` (sphere / cylinder / cube), `cone`, and `line` shape reads; the model
  places the aim egocentrically and the tracker computes the catch (no coordinates surfaced).
- **`/refine-prompts`** skill and prompt-writing conventions in `CLAUDE.md`.

### Changed
- Prompt refinements across agents and skills (dedup, tightened scope, SRD-safe combat examples).

## [0.2.0] — 2026-07-14

### Added
- Fenced control channels (`<turn-reminder>` / `<correction>` / `<prepared-context>`), the deterministic
  session-wrap nudge with a TUI context-usage readout, and session-completion tracked as a disk fact.

### Changed
- Disabled opencode auto-compaction in favor of the deterministic wrap; documented context management
  in `SPEC.md` / `README.md`.

## [0.1.1] — 2026-07-05

### Fixed
- Windows: force UTF-8 on stdio and subprocess text pipes.

## [0.1.0] — 2026-06-24

### Added
- Initial release: the D&D campaign-management framework over opencode — setup → play → reconcile
  orchestrator, agents, skills, and the TUI.
