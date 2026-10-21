# Benchmark — gm-llm as a tiered scaffolding instrument

Plan of record for the benchmark. What the system is → [README.md](README.md); the product it
measures → [luna.md](luna.md); combat → [combat.md](combat.md).

**Sequencing and status live in `ROADMAP.md` track benchmark**, which points at the B-numbered
stages below by number. This doc defines what each stage *is* and the contract it has to meet; it
does not say what is next or what has landed.

## Goal

Make gm-llm double as a benchmark: an LLM runs a full session against an autoplayer, and its score
is the number and severity of the violations found in its play. Tiers scale back the scaffolding —
from the full product (`low`: its prompts, skills, prepared context and stage structure) down to
bare (`high`: the session plan, the file layout, the dice tool and the wrap tool). **Every tier is
checked and scored identically, and no tier feeds a check back to the DM.** Checks run after play.

The current target is `low`: getting the most out of GPT-6 Luna on the full product. What `medium`
and `high` contain is decided after `low` has a banked baseline. The subject model is a separate
axis — `mimo-v2.6-flash-free` can be run against `low` too.

The subject is the DM playing well, never the checker catching it failing.

## Principles

1. **The product is the `low` tier.** The benchmark never changes product behavior: a run differs
   from real play only in who the player is and in being archived.
2. **Instrument vs. subject.** The *subject* is everything the product's model-facing surface is
   made of: `dm-runner`, `dm`, `log-extractor`, the authoring subagents, their skills and briefs. The
   *instrument* is the after-play checker, the grader, the rubric and the scoring. The instrument is
   pinned independently of the subject. The between-session gates belong to the product — they
   correct in real play, so they correct in a benchmark run too, and their verdicts are archived.
3. **Runtime captures; it never judges.** Play writes a raw JSONL archive. Checking and grading are
   separate offline passes over it, and their output is derived data: a rubric or checker revision
   re-checks history instead of invalidating it.
4. **Tiers are asset sets.** A tier is the set of model-facing files placed in the run directory;
   `low` is the shipped assets. The product never resolves tiers.
5. **Scores compare within a condition.** Tier, subject model and reasoning variant, fixture, turn
   cap, prompt fingerprint, instrument fingerprint and rubric are all condition fields, and a report
   refuses to pool across them.

## The pipeline

### Run — `bench run`

- Copy the template and the fixture's campaign into a fresh run directory and `git init` it. The
  tier's assets go in; `--subject-model` and `--subject-variant` rewrite the subject agents'
  model and reasoning variant.
- Player feedback points at the fixture's copy, never the user's own.
- A `conditions` event stamps the fixture id, tier, turn cap, whether reconcile runs, every agent's
  and subagent's model and reasoning variant, the prompt fingerprint and the gm-llm version.
- The autoplayer is Luna. `player.md` holds its rules, and two skills cover the situational parts:
  `player-combat` (its turn in a fight) and `player-rolls` (the DM asked for a roll). Its first
  message carries the character packet and the fixture's story-so-far recap; every later message is
  the DM's text in `<dm>…</dm>`, marked `<combat-turn>` on the PC's slot in a fight.
- Play runs to `task_complete`, with a hard turn cap as the safety net (each PC combat slot counts).
  Each combat beat archives the tracker's committed and pending frames.
- Reconcile follows a natural close unless `--play-only`.
- Outcomes are `complete`, `cap`, `incomplete` (resumable with `--resume`) or `failed`.

### Check — `bench check`

- **One rolling Luna checker session per run.** Its workspace is a pristine copy of the fixture's
  start-of-session campaign, because reconcile has since rewritten the run directory. The canon is
  loaded once.
- Turns are fed in play order: the player's message, the DM's text, the tools it called, and for a
  combat beat the tracker frames. The checker therefore sees the transcript only up to and including
  the turn it is judging.
- For each turn it submits structured findings through a tool — which check (canon, conduct or
  combat), the claim, the evidence, a category guess — or an empty list. A mistake it already
  flagged on an earlier turn is marked as continuing that finding rather than raised again; the
  rolling context is what makes that possible. A turn with no submission after one nudge is recorded
  `defaulted`.
- Output goes to its own `checks-<run>.jsonl`; the play archive is never rewritten.

### Grade — `bench grade`

- `openai/gpt-6.1-sol` at `high` reasoning, **one session per run**, with read access to the pristine
  start canon, the run's transcript and its checks, and the campaign at the end of the run for the
  stage findings. A run that hasn't been checked is not graded.
- Each finding is **confirmed or rejected**. A confirmed finding gets a severity, a category, a
  one-line rationale and `duplicate_of`; a rejection is a checker false positive. Stage-gate
  findings and canon-lint misses are graded the same way.
- The grades file opens with a header (rubric label, instrument fingerprint, grader model and
  variant). Grading is idempotent per header; `--double` grades a sample twice and reports agreement.

### Report — `bench report`

- The severity vector beside a 0–100 integrity score: severity points (steep — a critical is worth
  three majors) over graded units, with five subscores sharing that denominator so the deficits
  decompose additively. The 0-point floor is a display calibration, retuned only from a banked
  baseline.
- **Instrument health with every batch:** the defaulted rate, checker precision (confirmed findings
  over all findings) and grader agreement. An unhealthy instrument invalidates the batch.
- Secondary signals: turns to wrap, a clean `task_complete` close, stage-gate correction rates,
  context growth.

## The fixture

`dev/fixtures/hollowfell`: a campaign with sessions 1–2 played and session 3 planned, so a run plays
session 3 against real prior canon. It is converted to the [luna.md](luna.md) layout by script.

- **The character packet is generated in code** from the PC sheet, state and knowledge ledger — one
  generation path for `bench` and `--player auto`, never a hand-merged file.
- **The story so far** is a recap of the past transcripts, generated once, reviewed by hand and stored
  in the fixture. Transcripts are exactly what the player saw, so the recap cannot leak a secret.
- **Feedback files tune the subject**, so they are curated whenever the fixture is refrozen.
- The fixture is provisional until a baseline is banked against it; refreshing it after that forces a
  re-baseline.

## The stages

Each stage is useful if the workstream pauses. The order stages are *worked* in is ROADMAP's
business.

### B0 — Capture layer

A structured score-event archive (`gm_llm/orchestrator/archive.py`, riding on `Logs`): one event per
turn and per stage gate, written alongside the logs under `.opencode/logs/`. *Exit: a played session
leaves a machine-readable archive sufficient to re-derive every number the benchmark reports.*

### B1 — Fixture and bench runner

The fixture, `bench run` with batches and `--resume`, and the conditions event. *Exit:
`bench run --runs 5` completes unattended and leaves five condition-stamped archives.*

### B2 — Grader and report

`bench grade` and `bench report` as specified above. *Exit: a batch turns into a one-page report
with distributions, not single numbers.*

### B3 — The `low` baseline

Size a batch from a Luna pilot, then bank an identical-condition distribution of the `low` tier:
scores, run-to-run variance, instrument health. The MiMo pilot
([`dev/fixtures/hollowfell/pilot-2026-07-29.md`](../dev/fixtures/hollowfell/pilot-2026-07-29.md))
supplies methodology, not the sample size. *Exit: a written baseline report with its complete
condition identity.*

### B4 — Golden prompt stream

Under the mock backend, record the exact `(agent, session, message)` stream for a scripted
setup → play → wrap → reconcile pass and diff future streams against it byte for byte. An intended
change to the stream is re-recorded in the round that makes it.

### B5 — Conditions and tiers

The tier as a real field, reasoning variants instead of temperatures, subagents in the conditions,
`--subject-model`, and feedback isolation.

### B6 — Autoplayer on Luna

`player.md` re-authored, the `player-combat` and `player-rolls` skills, the generated packet and the
story-so-far recap.

### B7 — After-play checker

`bench check` as specified above, with checker prompts written for that role. The retired in-play
check skills hold the canon, conduct and combat checks to start from:
`git show 74fb69b^:gm_llm/assets/opencode/skills/<check-turn|check-conduct|check-combat>/SKILL.md`.

### B8 — Grader rework

Sol at `high`, one session per run, confirm or reject, file access, checker precision in the report.

### B9 — `medium` and `high` tiers, and ablations

Define what each tier strips, from what the `low` baseline shows, and run focused ablations of
observed mechanisms.

### B10 — Benchmark proper

Batches per condition, reports, and a methodology writeup.

## Out of scope — and the condition that would bring each one in

- **In-loop correction for the product's turns** — none at any tier. **In when** a focused
  experiment shows correction improves the game enough to pay for its latency.
- **Benchmarking setup** — fixtures sidestep it. **In when** setup quality is a claim the benchmark
  wants to make.
- **Multiple fixtures**, with per-scenario normalization. **In when** a single fixture's
  idiosyncrasies are shown to move a comparison.

## Risks

| Risk | Mitigation |
| --- | --- |
| Run-to-run variance swamps differences | B3 measures variance first; grow the sample or sharpen the rubric before drawing conclusions |
| Luna checking Luna flatters Luna | Sol confirms every finding with file access; checker precision is reported; an independent sweep of the drafts is possible from the archive |
| The rolling checker anchors on what it already flagged, over- or under-noticing that kind of mistake afterwards | Sol re-checks each finding against the files; an independent sweep of the archived turns can measure recall |
| Instrument edited in place | Prompt and instrument fingerprints in every header; grading is idempotent per fingerprint |
| Rate limits make batches slow | Resumable runs; conditions stamped so partial batches stay usable |
| Fixture drifts from the layout | A layout change re-converts the fixture and forces a re-baseline |
