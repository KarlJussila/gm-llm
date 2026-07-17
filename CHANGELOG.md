# Changelog

All notable changes to gm-llm are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project uses `0.x` versioning
(minor = a feature set or new mode, patch = fixes and small changes — see `CLAUDE.md`).

There is no PyPI publish: a "release" is the version-bump commit, which live campaigns pick up via
`pipx reinstall` + `gm-llm update`. The single source of the version is `gm_llm/__init__.py`.

## [Unreleased]

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
