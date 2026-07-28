# Findings

A **per-round record**, append-only: each Part records one round as it happened. Numbers and
"next round" notes are **point-in-time** — correct for their Part, *not* kept up to date as
later rounds land. For the live state read `HANDOFF.md`, not this file. Read a Part here for
the *reasoning* behind a decision, or for precedent on a problem you have hit again.

House heading form, so the index can be generated: `# Part N — Subject: what it's about (YYYY-MM-DD)`.

## Contents

| Part | Round | What it's best read for |
|---|---|---|
| [1](#part-1--setup-standing-up-the-handoff-round-loop-2026-07-27) | setup | Why the gate is `python dev/test_*.py` and not pytest; why bench counts stay out of the generated block |

## Recurring threads (the classes worth knowing)

- **One fact, two homes — the copy rots.** CLAUDE.md and `dev/MAINTAINING.md` both stated
  the versioning rule; MAINTAINING's copy was stale by a whole build-config change. Whenever
  a rule gets restated, the restatement is the defect. `lint_docs.py` check 7 encodes the
  specific instance. (Part 1)

# Part 1 — Setup: standing up the handoff-round loop (2026-07-27)

## The gap

Planning lived in four root docs (`BENCHMARK.md`, `PLAN.md`, `COMBAT.md`, `SPEC.md`) with no
current-state doc, no sequenced roadmap across them, and no archive. Each doc carried its own
private roadmap — BENCHMARK's B0–B9, PLAN's phases — so "what is next" required reading all
of them and inferring. Nothing recorded *why* a call was made beyond the git log.

The trigger was a concrete question with no home: expanding `6b4246f`'s play-axes work into
real frontend/mode modularity. It is not packaging (PLAN.md), not the benchmark (BENCHMARK.md),
and not combat — so under the old shape it had nowhere to go but a section in a doc it does
not belong to.

## What the round does

Stands up the five-doc loop per the `handoff-rounds` method: `CLAUDE.md` (stable orientation,
gains § How to run things), `HANDOFF.md` (current state), `ROADMAP.md` (sequenced remaining
work across all tracks), `design/findings.md` (this archive), `design/open-questions.md`.
Existing root docs are kept as **plan-of-record docs** that ROADMAP points at, not dissolved —
they hold design detail that ROADMAP must not swell to absorb. `design/frontends.md` is new
and is the plan of record for the work that triggered the round.

Tooling landed in the same round rather than deferred (bootstrap.md steps 7–9): `tools/status.py`
with `--write`/`--check`, `tools/lint_docs.py` with nine checks, and `.claude/skills/close-round/`.

**The gate already existed and is green.** `python -m compileall gm_llm` plus each
`dev/test_*.py` run as a script. That precondition being met is why the loop is worth standing
up here at all.

### Non-obvious calls

**The gate is not pytest, and the lint enforces that.** `dev/test_*.py` are standalone scripts
using a homegrown `tmp` helper, so `python -m pytest dev/` produces ~47 collection errors that
are pure convention mismatch — every one a `fixture 'tmp' not found`. A cold session will reach
for pytest first and read the result as a broken repo. `lint_docs.py` check 8 fails any doc
that sends it there. Converting the suite to pytest is a legitimate future task, but it is a
change to the gate, so it does not happen in the round that defines the gate.

**Bench batch state is deliberately absent from `status.py`.** Counting runs by outcome
(complete / capped / reconcile-pending) is exactly the number this round hand-derived with a
throwaway script — the smell the method names, "if you had to write a one-off script to count
something, that script should have been a tool." But `bench-out/` is gitignored and
machine-local, so putting it in the generated block would make `--check` fail differently on
every clone. It belongs in the bench CLI instead; ROADMAP carries it as `bench status`.

**A generator can be wrong in a way prose can't be — and it still beats prose.** Writing
HANDOFF by hand, this round typed "2 session dirs" for the bench fixture. `status.py` then
emitted **9**, because its glob counted flat files (`session-1.md`, `-plan`, `-notes`,
`-transcript`) as though sessions were directories. Both numbers were wrong, but differently:
the hand-typed one was a *guess*, the generated one was a *bad derivation*. The second kind is
findable — it is one function, it is read every round, and fixing it fixes every future round.
The first kind is invisible and recurs forever. The corrected metric reports played vs planned
and which session bench will actually open, which is the fixture's real shape and matches
BENCHMARK.md's description of it.

**Effort levels do not mean what they mean in the reference project.** There, `effort: low` is
safe because `validate.py` is a real oracle. Here the gate proves the *harness* works and says
nothing about whether a prompt change made the DM better — no score baseline is banked (BENCHMARK
B3). So **prompt-prose rounds are never low effort** regardless of how mechanical they look, and
the benchmark track is load-bearing for the method rather than just another track. ROADMAP's
effort table states this.

## Declared lossiness / deferrals

- **No history backfilled.** Part 1 is today. The ~30 commits of combat work and the bench
  workstream are not reconstructed into Parts — git holds them and inventing an archive would
  be worse than not having one.
- **`dev/MAINTAINING.md` was fixed, not deferred.** The plan had been to leave it failing so
  the fix was forced rather than remembered — but that would have ended the round that
  *establishes* "a red gate is this round's problem" with a red gate. Its versioning section
  now points at CLAUDE.md instead of restating it, and its release checklist points at the
  gate instead of copying it. The lint check stays: it is cheap, and it now guards a rule
  that is correct rather than documenting one that isn't.
- **Uncommitted bench work was left alone.** The working tree carries in-flight changes to
  `gm_llm/bench/runner.py`, `scoring.py`, `dev/test_bench.py`, and `CHANGELOG.md` (the
  reconcile-resume half of `--resume`). Not this round's work and not committed by it.

## Green bar

`python -m compileall gm_llm` clean; all ten `dev/test_*.py` scripts pass;
`tools/status.py --check` and `tools/lint_docs.py` pass.
