# Benchmark — gm-llm as a tiered scaffolding instrument

Plan of record for the benchmark. What the system is → [README.md](README.md); combat →
[combat.md](combat.md).

**Sequencing and status live in `ROADMAP.md` track benchmark**, which points at the B-numbered
stages below by number. This doc defines what each stage *is* and the contract it has to meet; it
does not say what is next or what has landed.

## Goal

Make gm-llm double as a benchmark: an LLM plays a full session (via an autoplayer), and its score
is the number and severity of violations flagged during play. Product profiles may use different
models, prompts, roles, and runtime support, but **every profile is observed and scored by the same
instrument whether or not the subject ever sees its feedback.**

The first comparison is intentionally historical rather than a synthetic ladder: Tier 0 is the
heavily scaffolded MiMo product; Tier 1 is a clean Luna product at `xhigh` reasoning. It asks how
much quality comes from the model versus the control system without requiring Luna to be built by
subtracting pieces from MiMo. Later ablations may vary guidance or runtime support once two concrete
profiles show which axes are real.

The subject is the runner playing well, never the checker catching it failing. A violation the gate
corrects is still a violation the runner committed and costs a real game a turn. In Tier 1 the gate
begins observe-only, so the instrument cannot become a weaker model steering a stronger one.

## Principles

1. **Tier 0 is frozen byte-for-byte.** The current prompts, agents, skills, and orchestration
   behavior are the legacy MiMo profile. They are never recomposed or used as the Tier-1 template;
   the golden stream protects them while shared substrate changes.

2. **Instrument vs. subject.** Assets partition into the *subject* (dm, dm-runner, the
   play/setup/planning skills, orchestrator briefs to them — what's being tested) and
   the *instrument* (narrative-checker, all `check-*` skills and briefs,
   `report-findings.ts`, the grader — what measures). The instrument has exactly one
   copy, no tier resolution path, ever, and is pinned to a fixed model/temperature
   independent of the subject model.

3. **Contract vs. craft.** *Contract* = externally necessary facts (campaign layout, tool semantics,
   completion, transcript and checkpoint outcomes). *Craft* = the model-facing way a profile gets
   there. Tier 1 shares the contract, not Tier 0's phrasing or decomposition.

4. **Concrete profiles before tier machinery.** Luna first runs through the smallest concrete
   second path that can exercise the shared substrate. Only after both profiles exist may common
   mechanics be extracted. A generic playbook, include system, axis matrix, or fragment library is
   justified by demonstrated duplication, not required in advance.

5. **Runtime captures; it never judges.** Scoring is decoupled from gating. Play emits
   a raw JSONL archive (drafts included); severity/category grading is a separate
   post-session pass by a strong model over the archive. The archive is ground truth;
   grades are derived data — a rubric revision re-grades history instead of
   invalidating it. `report_findings` keeps its current schema; the in-loop checker's
   workload is never perturbed.

6. **Measure the profile being developed.** A MiMo baseline no longer gates Luna work. Tier 0 is
   preserved by its golden stream; Luna gets a diagnostic run before product design and a baseline
   once its end-to-end path is viable. No pre-Luna score can validate Luna prose.

7. **Scores compare within a condition.** Profile, subject model, reasoning level, prompt identity,
   correction delivery, and fixture are all condition fields. Cross-profile deltas describe whole
   product behavior, not a single ladder of difficulty.

## Layout (target)

```
gm_llm/
  assets/
    opencode/            # frozen Tier-0 MiMo assets
    profiles/
      luna/              # complete Tier-1 model-facing surface, authored independently
  orchestrator/          # shared substrate plus the concrete profile seams Luna proves necessary
  bench/                 # not shipped in the wheel
    runner.py            # drives Game with the player agent against a fixture
    grade.py             # post-session severity/category grading over the archive
    scoring.py           # archive + grades → report
dev/
  fixtures/              # frozen campaign(s): world, character packet, session-1 plan
                         # (the `bench` group lives in gm_llm/bench, wired into gm_llm/cli.py
                         #  and registered only from a checkout)
```

Tier 0 keeps its flat opencode skill tree. The Luna profile owns only the model-facing assets its
observed behavior calls for; stable plugins and campaign templates remain shared substrate rather
than being copied into each profile.

## The stages

Each stage is useful if the workstream pauses. A profile baseline happens only after that product
path and its condition identity are viable. The order stages are *worked* in is ROADMAP's business.

### B0 — Capture layer *(code only, no model-facing change)*

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

Promote the autoplay harness (the scripted `player` agent) to benchmark grade.

- A **provisional** fixture campaign under `dev/fixtures/hollowfell`: a `gm-llm` campaign's
  `campaign/` (world, canon, the Dallid PC + play packet at `campaign/documents/`, sessions
  1–2 played and the session-3 plan — so bench plays **session 3** fresh, with real prior
  canon). Runs copy it to a temp dir; the source is never played in place. **We do not truly
  "freeze" it until benchmark 1.0** — reproducible-input-across-time only pays off once we're
  banking baselines (B3+). Until then it's *refreshed* from the live campaign (and `--fixture
  <dir>` can point anywhere), so iteration doesn't fight a stale snapshot.
  - **The feedback files are part of the frozen instrument.** `check-conduct` reads
    `campaign/feedback/session-run.md`, so whatever the fixture carries tunes what the
    checker enforces (suppress-only since the fix — feedback can excuse a flag, never
    raise one — but its *content still shifts the instrument*). When freezing or
    **re-freezing from a played campaign, curate or empty the feedback files** so an
    accumulated quirk doesn't silently bake into the rubric; any change forces a
    re-baseline like other fixture drift.
- `bench run`: pinned player model/temperature, pinned checker model, fixed turn
  budget, optional post-session reconcile (stage gates give post-session scores for
  free). Batch mode: N runs with rate-limit resilience (the `ping` machinery's
  lessons apply — expect overnight batches on the free tier). A run whose backend gives
  up mid-play (a sustained rate limit) is recorded `incomplete`, not failed — its
  transcript + archive persist — and `bench run --resume` continues every incomplete run
  in `--out` in place (same archive, continuous turn ids), so a cap that trips overnight
  doesn't burn the session's progress.
- Every run records its conditions (models, temps, tier, fixture id, gm-llm version)
  into the archive header. A comparison across mismatched conditions should be
  impossible to make by accident.
- **[Prereq to finalize] Standardize the player-end of the contract.** The player side has
  been loose, and it needs tightening before the bench is finalized. Pin all three: **where**
  the play packet lives (root vs. `campaign/documents/` — today's `character_packet` path is a
  stopgap), **how** it's generated (hand-merged from the player-known layer right now — see the
  auto-runner digest-regeneration item in B-later), and **how** it's loaded (`character_packet`
  in `fixture.json` for bench; `--character` in `gm-llm dev autoplay`). One canonical home, one
  generation path, one load contract.

*Exit: `bench run --runs 5` completes unattended and leaves 5 condition-stamped archives.*

### B2 — Grader + report

- `bench grade`: per flagged violation (or per session), a strong model at temperature 0
  reads the checker's prose report plus turn context and assigns severity/category via
  a structured tool call. Offline, decoupled from play — no rate coupling, one finding
  per brief if focus demands it.
- A versioned severity rubric doc (the grader brief embeds it; the archive records the
  rubric version used). One grading unit per *violation* — a checker report enumerating
  three problems on one turn grades as three. Deduplication of a violation counted twice:
  the same mistake persisting across turns, or one draft tripping both `check-turn` and
  `check-conduct`. Per-session calibration.
- **The score model** (`scoring.score_violations`): each dedup'd violation costs penalty
  points by severity (steep — a critical is worth three majors), normalized by graded units
  into a rate, mapped to a 0–100 integrity score. Subscores on five dimensions (canon
  fidelity, information discipline, player agency, mechanical integrity, record integrity)
  use the same denominator, so the composite comes from the total penalty rather than an
  average of subscores and the deficits decompose additively. Reported *beside* the severity
  vector, never instead of it. The 0-point floor rate is a display calibration — retune it
  only from a banked profile baseline, beginning with Luna.
- Instrument reliability: `bench grade --double` grades a sample twice and reports
  agreement. Also surface the `defaulted`-verdict rate — a checker not doing its job
  must never read as the subject improving.
- `bench report`: archive + grades → per-run and per-batch summary (violation count by
  severity, correction rate, defaulted rate, turns-to-wrap, clean `task_complete`
  close, stage-gate outcomes).

*Exit: a batch turns into a one-page report with distributions, not single numbers.*

### B3 — Profile baseline batch

- Identical-condition runs for a viable product profile, stamped with profile, subject model,
  reasoning level, correction-delivery mode, and prompt/instrument fingerprints.
- Deliverables: the score distribution, run-to-run variance, grader agreement, and defaulted rate.
- Size a batch from a pilot under that same profile. The Tier-0 pilot at
  [`dev/fixtures/hollowfell/pilot-2026-07-29.md`](../dev/fixtures/hollowfell/pilot-2026-07-29.md)
  remains methodology evidence, not a Luna sample-size calculation or a gate on Luna work.

*Exit: a profile-specific written baseline report checked in with its complete condition identity.*

### B4 — Golden prompt-stream test *(free regression armor)*

- Under the mock backend, record the exact `(agent, session, message)` stream the
  orchestrator emits for a scripted setup → play → wrap → reconcile pass. Check the
  recording in; a test diffs future streams against it byte-for-byte.
- This is the cheap guard that shared-substrate changes do not silently rewrite Tier 0.

### B5 — Profile identity and selection

- Stamp profile and reasoning level alongside the existing per-agent model/temperature identity.
- Let the bench select an already-built product profile using the same profile boundary as normal
  play. The benchmark does not invent its own tier resolver or assemble a product from overrides.
- Reject accidental pooling across any changed condition.

*Exit: the same fixture can run through either product profile and cannot be compared under a
misidentified condition.*

### B6 — Observe-only Tier-1 instrument

- Run the common checker and archive against Luna drafts without delivering MiMo correction prose
  back to Luna.
- Keep the raw draft, verdict, default/failure state, and final player-visible turn distinct.
- Verify that attaching the instrument does not change the Tier-1 prompt stream or output path.

### B7 — Luna baseline and focused ablations

- Bank the Tier-1 Luna-at-`xhigh` baseline only after the end-to-end profile is viable.
- Use focused ablations to answer observed questions (for example correction delivery on/off or a
  context preload present/absent). Do not manufacture a full axis matrix in advance.
- A Tier-0 batch is optional comparison evidence, not a prerequisite and not pooled with Luna.

### B8 — Benchmark proper

- Batches per complete condition; reports; publishable methodology writeup.
- Cross-profile results are presented as whole-product comparisons. Only controlled ablations make
  narrower causal claims about a particular mechanism.

## Out of scope — and the condition that would bring each one in

Decisions, not a backlog: each of these is deliberately *not* part of the benchmark, with the
trigger that would change that. Unresolved questions live in
[open-questions.md](open-questions.md) instead.

- **Independent audit pass** — a strong model re-sweeps archived *drafts* for violations the
  in-loop checker missed (detection recall). The archive already supports it. **In when** a
  cross-model claim needs defending.
- **In-loop severity for the *product*** (e.g. correct only above a threshold) — a separate
  experiment, A/B'd against the archive to watch the defaulted-verdict rate. **In when** the
  correction rate itself becomes the thing under study.
- **Benchmarking the setup phase** — fixtures sidestep it. **In when** setup quality is a claim
  the benchmark wants to make.
- **Multiple fixtures / scenario diversity**, with per-scenario score normalization. **In when** a
  single fixture's idiosyncrasies are shown to move a tier comparison.

## Measurement methodology (summary)

- **Fixed per batch:** fixture, profile, subject model + reasoning level, checker model, turn
  budget, correction-delivery mode, gm-llm version, rubric version. All stamped into the archive.
- **Score the draft, always** — the same measurement whether a profile corrects it or leaves the
  instrument observe-only. Corrections are recorded as their own signal (correction rate).
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
| Shared-substrate work subtly changes Tier 0 | Golden stream test (byte-level); a confirmation batch only when the prompt stream cannot cover the seam |
| Free-tier rate limits make batches slow/flaky | Batch runner designed for overnight, resumable runs; conditions stamped so partial batches stay usable |
| Rubric revisions invalidate history | Grades are derived from the raw archive — re-grade, never re-play |
| Fixture drifts from evolving canon-conventions | The fixture is frozen per benchmark epoch; a conventions change that touches the fixture forces a fixture re-generation **and** a re-baseline (accept and document) |
| A generic profile abstraction bakes in Tier-0 assumptions | Build the concrete Luna path first; extract only contracts both live profiles actually share |

## Decisions (updated 2026-08-14)

1. **Grader/checker instrument model** — the common checker stays MiMo (preserves Tier 0's
   gate) but begins observe-only for Tier 1. MiMo isn't the target instrument for any part, but it's
   what's available; this is a niche prototype and a stronger instrument can ship as a
   V2 re-grade (grades are derived data). No cross-epoch consistency promised yet.
   The grader model is picked at B2.
2. **Where `bench/` lives** — `gm_llm/bench/`, wheel-excluded like `dev/`, for clean
   imports.
3. **Turn budget** — play to natural close (`task_complete`) with a hard turn cap as
   the safety net. Cap breaches are stamped into the archive; turns-to-wrap stays a
   meaningful signal.
4. **Reconcile** — `bench run` includes the selected profile's post-session outcome by default,
   with a `--play-only` flag for cheap iteration. Profiles may reach that outcome through different
   internal stage graphs.
5. **Profile identity** — product profiles use stable numeric identities: Tier 0 is the frozen MiMo
   path and Tier 1 is Luna at `xhigh`. Reasoning levels are condition fields, not tier names. Existing
   archives stamped `low` remain historical data; B5 owns the forward identity migration rather than
   pretending `low` means both a product and a reasoning setting.
