# BENCHMARK — gm-llm as a tiered scaffolding benchmark

The design doc and roadmap for the benchmark workstream. `SPEC.md` describes what the
system *is*; `PLAN.md` carries the packaging/Windows work; this doc carries the benchmark.

## Goal

Make gm-llm double as a benchmark: an LLM plays a full session (via an autoplayer),
and its score is the number and severity of violations flagged during play. Tiers scale
back the scaffolding — from the full product (prompt engineering, skills, per-turn
reminders, checker-fed corrections) down to *"here's the session plan, here's the notes
layout, here's the dice tool and the wrap tool; run the session."* **Every tier is
checked and scored identically, whether or not the model ever sees the feedback.**

The benchmark measures how much of the product's quality comes from structure
(orchestration, reminders, corrections) versus craft prose (skills, guardrails) versus
the model itself — and how gracefully a given model degrades as scaffolding is removed.

## Principles (settled in design discussion)

1. **Tier 0 is the product, byte-for-byte.** The current prompts, agents, and skills
   *are* tier 0. They are never recomposed, templated, or routed through includes — the
   interwoven contract-and-craft texture is tuned for the modest model and stays intact.
   The product path never changes behavior because the benchmark exists.

2. **Instrument vs. subject.** Assets partition into the *subject* (dm, dm-runner, the
   play/setup/planning skills, orchestrator briefs to them — what's being tested) and
   the *instrument* (narrative-checker, all `check-*` skills and briefs,
   `report-findings.ts`, the grader — what measures). The instrument has exactly one
   copy, no tier resolution path, ever, and is pinned to a fixed model/temperature
   independent of the subject model.

3. **Contract vs. craft — for new tiers only.** *Contract* = mechanical facts every
   tier must state (campaign layout, tool semantics, wrap protocol, notes format).
   *Craft* = pacing, agency, spoiler discipline, the turn algorithm — the experimental
   variable, deliberately different per tier, never synced. Shared contract fragments
   feed tiers 1–2 by composition; tier 0's sync with the fragments is enforced by a
   conformance **test** (facts present, not phrasing matched), never by composition.

4. **Tiers are data: a prompt namespace + a playbook + axis flags + a skill set.** The
   orchestrator's invariant skeleton (dispatch → gate → score event → checkpoint) is
   the engine; each tier supplies a *playbook* — its stage sequence and briefs — plus
   runtime-support flags. Two independent axes, kept separate in the config even though
   shipped tiers are named points in the space:
   - **guidance** — prompt verbosity, which skills exist, playbook granularity;
   - **runtime support** — per-turn reminder, wrap nudges, canon preload, whether gate
     verdicts are delivered as corrections (the gate itself always runs).

5. **Runtime captures; it never judges.** Scoring is decoupled from gating. Play emits
   a raw JSONL archive (drafts included); severity/category grading is a separate
   post-session pass by a strong model over the archive. The archive is ground truth;
   grades are derived data — a rubric revision re-grades history instead of
   invalidating it. `report_findings` keeps its current schema; the in-loop checker's
   workload is never perturbed.

6. **Baseline before restructuring.** No refactor lands until the current system's
   score distribution is measured. Behavior-preserving refactors are verified by a
   golden prompt-stream test (byte-level, free); prose-changing work is verified
   against the score baseline (model runs, expensive).

7. **Scores compare within a tier, not across tiers.** Tier 0's corrections change the
   downstream trajectory — different condition, not just a different score. Cross-tier
   deltas describe *scaffolding sensitivity*, not a single ladder of difficulty.

## Layout (target)

```
gm_llm/
  assets/
    opencode/            # unchanged — the product, which IS the `low` tier
    fragments/           # contract prose, single source: layout, tools, wrap, notes
    tiers/
      medium/            # "standard" overrides: rewritten barebones agent/*.md, prompts/*.md
      high/              # "bare" overrides: minimal kickoff + near-empty agent files
  orchestrator/          # engine: Game/Gate/commit/markers; playbook-driven; score events
  bench/                 # not shipped in the wheel
    tiers.py             # Tier profiles (namespace + playbook + axes + skills)
    playbooks.py         # the stage sequences, as data
    runner.py            # drives Game with the player agent against a fixture
    grade.py             # post-session severity/category grading over the archive
    scoring.py           # archive + grades → report
dev/
  fixtures/              # frozen campaign(s): world, character packet, session-1 plan
  cli.py                 # grows a `bench` command (batch runs, grading, reports)
```

Skills stay flat under `assets/opencode/skills/` (opencode dictates that); a tier either
ships a skill or doesn't — skills are only ever tier-0 content. If the benchmark ever
needs a parallel prompt tree, the design has gone wrong.

## Roadmap

Phases are ordered so every step is useful even if the workstream pauses, and so the
expensive step (the baseline batch) happens exactly once, on the final instrument.

### B0 — Capture layer *(code only, no model-facing change)* — **landed 2026-07-15**

Emit a structured score-event archive from the existing gate paths.
Implementation: `gm_llm/orchestrator/archive.py`, riding on `Logs` (an `archive`
member, lazily headed); events emitted from `loop.py` (turn), `planner.py` (plan),
`reconciler.py` (digest/feedback/propagation/lint), `setup.py` (init). Verified by
`dev/test_archive.py`.

- One JSONL event per runtime turn from `loop.py`/`gate.py`: player message, draft,
  final, `corrected`, both verdicts (check name, passed, `defaulted`, full prose
  report), canon section count, context usage, timestamps, session/turn ids.
- One event per stage gate (`check-plan`, `check-digest`, `check-feedback`,
  `check-propagation`, `check-init`, the completeness lint) from
  `planner.py`/`reconciler.py`/`setup.py`.
- Location: alongside the existing logs in `.opencode/logs/` (gitignored), one file per
  run. This is largely the data already formatted for `orchestrator-checks.log`,
  structured.
- **Drafts are archived from day one** — the future audit pass (B-later) depends on it.

*Exit: a played session leaves a machine-readable archive sufficient to re-derive every
number the benchmark will ever report.*

### B1 — Fixture + bench runner

Promote the `dev/cli.py play` harness (the scripted `player` agent) to benchmark grade.

- Check in one frozen fixture campaign under `dev/fixtures/`: a `gm-llm init`-ed
  project's `campaign/` with world, canon, a character (the `dallid` packet exists),
  and a session-1 plan. Runs copy it to a temp dir; the fixture repo itself is never
  played in place.
- `bench run`: pinned player model/temperature, pinned checker model, fixed turn
  budget, optional post-session reconcile (stage gates give post-session scores for
  free). Batch mode: N runs with rate-limit resilience (the `ping` machinery's
  lessons apply — expect overnight batches on the free tier).
- Every run records its conditions (models, temps, tier, fixture id, gm-llm version)
  into the archive header. A comparison across mismatched conditions should be
  impossible to make by accident.

*Exit: `bench run --runs 5` completes unattended and leaves 5 condition-stamped archives.*

### B2 — Grader + report

- `bench grade`: per flagged violation (or per session), a strong model at temperature 0
  reads the checker's prose report plus turn context and assigns severity/category via
  a structured tool call. Offline, decoupled from play — no rate coupling, one finding
  per brief if focus demands it.
- A versioned severity rubric doc (the grader brief embeds it; the archive records the
  rubric version used). Deduplication of a violation flagged across consecutive turns;
  per-session calibration.
- Instrument reliability: `bench grade --double` grades a sample twice and reports
  agreement. Also surface the `defaulted`-verdict rate — a checker not doing its job
  must never read as the subject improving.
- `bench report`: archive + grades → per-run and per-batch summary (violation count by
  severity, correction rate, defaulted rate, turns-to-wrap, clean `task_complete`
  close, stage-gate outcomes).

*Exit: a batch turns into a one-page report with distributions, not single numbers.*

### B3 — Baseline batch *(the measurement, before any refactor)*

- 5–10 identical-condition tier-0 runs on the **current, untouched** code and prompts.
- Deliverables: the score distribution; the run-to-run variance (if variance is
  comparable to the effect sizes we care about, that's a finding — fix sample size or
  instrument before proceeding); grader agreement; defaulted rate.
- This baseline anchors everything after it. Nothing model-facing changes until it's
  banked.

*Exit: a written baseline report checked into `dev/fixtures/` or alongside this doc.*

### B4 — Golden prompt-stream test *(free regression armor)*

- Under the mock backend, record the exact `(agent, session, message)` stream the
  orchestrator emits for a scripted setup → play → wrap → reconcile pass. Check the
  recording in; a test diffs future streams against it byte-for-byte.
- This is the cheap guard for behavior-preserving refactors: B5 must diff clean.

### B5 — Playbook extraction *(refactor, verified twice)*

- Extract the invariant engine from `loop.py`/`planner.py`/`reconciler.py`/`setup.py`;
  move the hard-coded sequencing into a tier-0 playbook (data). Same briefs, same
  order, same session boundaries, same commits.
- Verify: (a) golden stream diffs clean — mandatory; (b) an optional tier-0
  confirmation batch matches the B3 distribution — if it doesn't, the golden test
  missed a surface, investigate before any tier prose is written.

*Exit: tier 0 reproduces current behavior through the playbook mechanism.*

### B6 — Tier plumbing

- `Tier` dataclass (guidance axis + runtime-support axis), `bench/tiers.py`.
- Tier-aware prompt resolution: `prompts/{tier}/{name}.md` overrides base; a minimal
  `{{include:fragment}}` mechanism — **used only by non-zero tiers**. Tier 0 resolves
  to the current files with no processing.
- Scaffolder learns tiers (bench-only; `gm-llm init` for users is always tier 0).
- Runtime-support flags wired: reminder off, wrap-nudge off, preload off, observe-only
  gate (check runs, correction brief withheld, archive records it either way).
- Conformance tests (in the `dev/test_completeness.py` style): every tier's assembled
  prompts state the contract facts (paths, tool names, wrap signal); agent frontmatter
  grants identical tools/permissions across tiers; every include resolves; every
  playbook references briefs and skills that exist.

### B7 — `high` tier ("bare") authoring

Author the extreme tier first — it's tiny, and it stress-tests the contract fragments:
*could a model actually run a session from only this?*

- Write the contract fragments (`campaign-layout`, `tools`, `wrap-protocol`,
  `notes-format`) — these become the single source the conformance test holds tier 0
  against, too.
- Minimal kickoff brief (fragments + "run the session"), near-empty agent files
  (frontmatter is contract: permissions, tools, model), pass-through turns, no skills.
- Collapsed post-session playbook: one "update the campaign records from this
  transcript, following the layout" stage; `check-propagation` still scores it.
- Shakedown runs; fix contract gaps the bare model trips over (each gap found here is
  a fact tier 1 must also state).

### B8 — `medium` tier ("standard") authoring

- Rewritten barebones prompts: role + contract, no guardrail prose (no pacing/agency/
  metagame lectures — a model that knows D&D should know). Calibrated by the tier-2
  experience; this is the hardest prose to write, hence last.
- Roughly tier-0's stage structure, pointed at the barebones namespace; runtime
  support off per the tier definition.

### B9 — Benchmark proper

- Batches per (tier × subject model); reports; publishable methodology writeup.
- The two-axis config enables ablations ("corrections on, craft prose off") — more
  interesting than a single blended score per tier.

### B-later (explicitly deferred)

- **Independent audit pass**: a strong model re-sweeps archived *drafts* for
  violations the in-loop checker missed (detection recall). The archive already
  supports it; build when cross-model claims need it.
- In-loop severity for the *product* (e.g., correct only above a threshold) — a
  separate experiment, A/B'd against the archive to watch the defaulted-verdict rate.
- Benchmarking the setup phase itself (fixtures sidestep it today).
- Multiple fixtures / scenario diversity; per-scenario score normalization.

## Measurement methodology (summary)

- **Fixed per batch:** fixture, player model + temperature, checker model, turn
  budget, tier, gm-llm version, rubric version. All stamped into the archive.
- **Score the draft, always** — the same measurement whether or not tier 0 then
  corrects it. Corrections are recorded as their own signal (correction rate).
- **Distributions, not points:** 5–10 runs minimum; report variance alongside means.
- **Instrument health reported with every batch:** defaulted-verdict rate, grader
  agreement. An unhealthy instrument invalidates the batch, not just a run.
- **Secondary signals:** correction rate, turns-to-wrap, clean `task_complete` close,
  stage-gate outcomes, context growth. Regressions often show here before the headline
  violation count moves.

## Risks

| Risk | Mitigation |
| --- | --- |
| Run-to-run variance swamps tier effects | B3 measures variance *first*; grow sample size or sharpen the rubric before drawing conclusions |
| Checker (mimo) misses violations → scores flatter the subject | Same detector across all tiers keeps comparisons internally valid; drafts archived from day one so the audit pass can quantify recall later |
| Playbook refactor subtly changes the model-facing surface | Golden stream test (byte-level) + optional tier-0 confirmation batch |
| Free-tier rate limits make batches slow/flaky | Batch runner designed for overnight, resumable runs; conditions stamped so partial batches stay usable |
| Rubric revisions invalidate history | Grades are derived from the raw archive — re-grade, never re-play |
| Fixture drifts from evolving canon-conventions | The fixture is frozen per benchmark epoch; a conventions change that touches the fixture forces a fixture re-generation **and** a re-baseline (accept and document) |
| Contract fragments and tier-0 prose drift apart | Conformance test asserts facts, not phrasing; runs in CI/dev tests |

## Decisions (settled 2026-07-15)

1. **Grader/checker instrument model** — the in-loop checker stays mimo (preserves the
   product's gate). Mimo isn't the target instrument for any part of this, but it's
   what's available; this is a niche prototype and a stronger instrument can ship as a
   V2 re-grade (grades are derived data). No cross-epoch consistency promised yet.
   The grader model is picked at B2.
2. **Where `bench/` lives** — `gm_llm/bench/`, wheel-excluded like `dev/`, for clean
   imports.
3. **Turn budget** — play to natural close (`task_complete`) with a hard turn cap as
   the safety net. Cap breaches are stamped into the archive; turns-to-wrap stays a
   meaningful signal.
4. **Reconcile** — `bench run` includes the post-session reconcile (wrap + stage gates)
   by default, with a `--play-only` flag for cheap iteration. The bare tier's collapsed
   pipeline remains a B7 design question.
5. **Tier names** — the LLM reasoning-effort tier names, tracking difficulty (how
   much the model must carry unaided): **`low`** (the product, formerly tier 0),
   **`medium`** (standard, formerly tier 1), **`high`** (bare, formerly tier 2).
   `xhigh` and `max` are reserved headroom — tiers can shuffle over and new,
   barer ones slot in without renaming what's shipped. These are the labels
   stamped into archives. Where this doc says "tier 0/1/2", read low/medium/high.
