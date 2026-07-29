# ROADMAP — all planned work, sequenced

The single sequence for everything that remains, with a **recommended effort level per task**.
What each task *is* lives in the linked plan-of-record docs — this file only orders the work
and says how hard to think about it.

How a session picks up and hands off: `CLAUDE.md` § Standing rules. The live "task now"
pointer is `HANDOFF.md` § Next task.

## Effort levels

| Effort | Use for | Discipline |
|---|---|---|
| **low** | Checklist work, fully specified, with the gate catching errors | Trust the gate; don't redesign in passing |
| **medium** | Specified implementation that still encodes a contract | The default |
| **high** | Decisions, contract reviews, first-of-kind work with no oracle | Spend it on choices that are expensive to reverse, never on labor |

**Prompt-prose work is never low.** The gate proves the harness works; it says nothing about
whether a prompt change made the DM better, and no score baseline is banked yet (track
**benchmark**, B3). Until one is, every change under `gm_llm/assets/opencode/` or
`gm_llm/orchestrator/prompts/` is at least medium and leans on the git-archaeology discipline
in `CLAUDE.md` § Writing prompts.

Fan-out to workers is a *method*, not a level: rows that name it mean the round batches menial
items out and the **driving session re-verifies every result**.

## frontends — mode × frontend modularity

Plan of record: [`design/frontends.md`](design/frontends.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 5 | Route console autoplay through `Lifecycle` | low | The last direct `Game` construction. Blocks nothing — duplication to retire, not a gap; needs `player_source()` to carry the resume story |

## recalibration — align the prompts with the runner-authority model

Plan of record: [`design/runner-authority.md`](design/runner-authority.md) — the six rules, the
audit these rows close, and § Delivery, which is why row 1 runs before the prose rows.

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | `turn-reminder` as an executable algorithm | high | **Runs first: it decides where every rule below can live.** The runner reads canon and skills on turn 1 and never again (§ Delivery), so today only the reminder and the checker reach a turn. Grant `dm-runner` `todowrite` (the one agent without it) and make the reminder a per-turn list with re-load *triggers*. If it takes, rules move back into skills and the reminder gets shorter; if not, they all compete for reminder space. Measurable without the grader |
| 2 | Re-cut `check-turn`'s new-canon test on plot impact (F5) | high | The checker examined the geologist and **passed** it as "consistent with canon"; it asks *does this conflict?* where rule 4 asks *does this touch the plot?* Keep the classes, change the test, widen intake past newly-*named* things — and narrow the preamble's divergence licence to player-initiated without re-opening the false positives it was written to stop |
| 3 | Enforce revelation against the plan's reveal flags (rule 5) | high | The plan already carries `(known)` / `(new reveal)` / `(stays hidden)` per clue, and neither `session-run` nor `check-turn` consults them. Needs those flags on the checker side — decide preloaded block vs. on-demand read |
| 4 | Author the runner-side rules (F1, F3, F4 + secondary) | high | `session-run` § Table craft holds none of the absolutes; `discoveries` binds the plan's mechanics and frees its content; `social-play` bounds what an NPC may *know* but not what may be invented in their mouth. Shape depends on row 1's outcome |
| 5 | Planner-side pass — `npc-plan` richness, the 30–40% rule, and whether DCs stay | medium | Every NPC trait the plan commits is one the runner cannot invent, so this is leverage on rule 4 rather than cleanup. Carries the DC decision (rule 1 makes them advisory; open whether `dm` keeps authoring them) |

## benchmark — the instrument

Plan of record: [`design/benchmark.md`](design/benchmark.md) (B-numbers are its sections).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | B1 prereq — pin the player-end contract | high | One home, one generation path, one load contract for the play packet; BENCHMARK calls it a prereq to finalizing the bench |
| 2 | B3 — bank the baseline batch | medium | Identical-condition tier-0 runs; **sized from the pilot, not from BENCHMARK's "5–10"** ([`dev/fixtures/hollowfell/pilot-2026-07-29.md`](dev/fixtures/hollowfell/pilot-2026-07-29.md)). Waits on track **recalibration** — a baseline of prompts about to be rewritten measures nothing |
| 3 | `bench status` — batch state without a throwaway script | low | Runs by outcome (complete / capped / reconcile-pending) is a number this repo keeps hand-deriving; `bench-out/` is gitignored so it can't live in `status.py` (Part 1) |
| 4 | B4 — golden prompt-stream test | medium | Free regression armor; B5 must diff clean against it |
| 5 | B5 — playbook extraction | high | Extract the invariant engine; verified twice (golden diff mandatory, confirmation batch optional) |
| 6 | B6–B9 — tier plumbing, then tier authoring | high | Not startable until B5; B7 (bare) is authored before B8 (standard) because the extreme tier stress-tests the contract fragments |

## live — shakedown against a real model

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | New-campaign shakedown (setup + character import) | medium | Owed since the prior plan; exercises the per-arc apply briefs and slimmed checker skills |
| 2 | Combat shakedown | medium | The whole tracker/loop/gate/craft stack is mock-verified only ([`design/combat.md`](design/combat.md)) |

## packaging — native Windows and easy setup

No plan-of-record doc: the design is settled and built. The portability rules that keep it
working are `dev/MAINTAINING.md` § Portability; what remains is validation and one decision.

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Validate on native Windows | medium | The biggest external unknown — opencode's own native-Windows maturity (clean server lifecycle, child-process teardown). Everything in our code is fixable; this needs a real Windows box. Probe `opencode.cmd` resolution, process-tree kill, paths with spaces, ANSI. Fallback if opencode itself is the problem (WSL is ruled out): pin a known-good opencode version and document it |
| 2 | Model configuration | high | Deferred by agreement; needs the campaign-vs-install ownership decision (`design/open-questions.md`) |

## docs — keep the loop honest

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Generate `findings.md` § Contents | low | Hand-maintained indexes fall behind the archive they index; do it before the archive is long enough to matter |
| 2 | Decide on pytest for `dev/test_*.py` | medium | Changes the gate, so it is its own round (`design/open-questions.md`) |
| 3 | `sessions/` → per-session directories | high | A large cross-cutting path refactor (orchestrator modules, briefs, skills, `canon-conventions` §2, tests) with no behavior change to show for it — it must be its own round and never a rider (`design/open-questions.md`) |

## Landed

| Track | Parts | Outcome |
|---|---|---|
| docs | 1 | The handoff-round loop stood up: five docs, `status.py`, `lint_docs.py`, `close-round`; `dev/MAINTAINING.md` reconciled |
| docs | 2 | Planning consolidated onto the loop: `SPEC.md`/`PLAN.md` absorbed and deleted, plan-of-record docs moved into `design/`, private roadmaps and backlogs stripped, lint checks 10–12 |
| packaging | 2 | Phase 1 (native-Windows portability) closed — its rules now live in `dev/MAINTAINING.md` § Portability |
| frontends | 3 | Step 1: the two `_play_combat`s unified into `orchestrator.play_combat`, bench's cap accounting preserved as the base and tested directly |
| frontends | 4 | Step 2: `PlayerSource` + `play_session` — one turn loop for the TUI, autoplay and bench; `--player auto --ui tui` filled in, and the TUI given a headless test |
| frontends | 5 | Step 3: `bench run` plays a `Lifecycle` — its own `Game`/player-session/reconciler wiring gone, the post-wrap tail now `wrap(on_stage=…)`, the test seam moved to `lifecycle_factory` |
| frontends | 6 | Step 4: `bench run --ui tui` — `BatchHooks`, a lifecycle attached per run, `BatchHeader`; watching made read-only and the comparability invariant asserted against a headless batch |
| recalibration | 8 | The ruleset settled (eight transcribed rules → six, one of them a positive) and the corpus audited against it: the runner path scores nothing on rules 1–4, and the session records show why — canon and skills are read on turn 1 and never again |
| benchmark | 7 | The five-run pilot read (**B3 itself is not banked** — the pilot is what says how to bank it): the grading instrument content-hashed, an error bar and a resolution figure on the score, thin subscores flagged. Its findings opened track **recalibration** and parked B3 behind it |

## Standing sync rules

- **Recalibration runs before B3, and suspends the freeze while it does.** The standing rule was
  "nothing model-facing changes before B3 banks the baseline" — sound while the prompts were
  believed correct, and inverted once they are not: baselining prompts that are about to be
  rewritten measures a system that will not exist. Track **recalibration** is therefore the one
  model-facing exception, and it closes before B3 opens. The freeze still binds every *other*
  model-facing change, and B3 is sized from the pilot, not from BENCHMARK's "5–10".
- **The pilot's scores do not survive recalibration.** The prompt fingerprint is part of a run's
  condition, so recalibrated runs cannot pool with pre-recalibration ones. What survives is the
  pilot's methodology (variance structure, grader reliability, the thin-dimension limit); the
  numbers describe a superseded subject. Harness-only work (frontends, packaging, docs) runs
  alongside freely throughout.
- **B4 lands before B5.** The golden stream is the only thing that makes the playbook
  extraction verifiable as behavior-preserving.
- **The live shakedowns can run at any time** and should run before, not after, a release that
  touches the orchestrator.
