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
| [2](#part-2--docs-consolidating-the-planning-docs-onto-the-loop-2026-07-27) | docs | Why `SPEC.md` and `PLAN.md` were deleted rather than moved; how a plan-of-record doc differs from a roadmap and a backlog |

## Recurring threads (the classes worth knowing)

- **One fact, two homes — the copy rots.** CLAUDE.md and `dev/MAINTAINING.md` both stated
  the versioning rule; MAINTAINING's copy was stale by a whole build-config change. Whenever
  a rule gets restated, the restatement is the defect. `lint_docs.py` check 7 encodes the
  specific instance. (Part 1)
  Part 2 found the same class three more times, all in docs wearing a "plan of record" label:
  every workstream doc carried a private roadmap beside ROADMAP's, two carried private
  backlogs beside open-questions', and `PLAN.md` claimed HANDOFF's job outright. Checks 10–12
  encode those. The pattern to watch for is a doc whose *label* says design and whose *content*
  says status.
- **A doc nothing verifies is a doc that is already wrong.** `SPEC.md` had rotted in four
  independent places — two stale top-level package paths, a "seven `check-*` skills" count that
  was eight, and a "forthcoming `combat-run`" that had shipped a minor version earlier — while
  being listed as a plan-of-record doc every session was told to trust. Nothing pointed at its
  § Features, nothing checked it, and it had been dragged along as living documentation only
  because sessions kept dutifully updating it. Deleting it was cheaper than maintaining it.
  (Part 2)

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

# Part 2 — Docs: consolidating the planning docs onto the loop (2026-07-27)

## The gap

Part 1 stood up the five-doc loop and **kept** `BENCHMARK.md`, `COMBAT.md`, `PLAN.md` and
`SPEC.md` as plan-of-record docs ROADMAP would point at. It reconciled `dev/MAINTAINING.md` and
stopped there — so the thing it had named as its own trigger survived it: *"each doc carried its
own private roadmap — BENCHMARK's B0–B9, PLAN's phases."* One round later the repo ran two
architectures at once, and a cold session picking up `HANDOFF.md` § Next task was one link away
from a doc that answered the same question differently.

Concretely, every track had two sequencers (ROADMAP's rows vs. B0–B9 / C0–C5 / PLAN's phases,
the latter carrying fourteen `[done]` / `**done**` / `landed <date>` markers), two backlogs
(`open-questions.md` vs. COMBAT § Open decisions and BENCHMARK § B-later — nine items, none on a
track, so `lint_docs.py` check 6 could not see them), and two current-state docs (`HANDOFF.md`
vs. `PLAN.md`, which opened by calling itself *"the active work-in-flight doc"*).

## What the round does

Deletes two docs, moves two, strips the rest back to design, and adds the three checks that stop
it recurring.

- **`SPEC.md` deleted, absorbed in three directions.** § Architecture / § Constraints /
  § Non-Goals / the durable half of § External Integrations became `design/README.md`, which is
  now both the routing table for `design/` and the "what the system is" doc — the shape the
  reference project uses, where `design/README.md` carries the model overview and no SPEC exists
  at all. § Repository Layout collapsed into README's existing § Layout (which was already more
  accurate). **§ Features was deleted outright**, not rehomed.
- **`PLAN.md` deleted, not relocated.** Roughly 70% `[done]` changelog; its live content was
  already three ROADMAP rows plus one open-question. The residue was the Windows portability
  scar tissue, and `dev/MAINTAINING.md` line 3 *already declared itself* the home for "the
  portability rules that keep Windows working" — it held the encoding half while PLAN held the
  process half. They merged into one § Portability with two subsections.
- **`BENCHMARK.md` → `design/benchmark.md`, `COMBAT.md` → `design/combat.md`.** Root now holds
  only the loop plus the user-facing manual; `design/` holds every plan of record. This also puts
  them under lint checks 1 and 2 for free, which is most of why the split was worth closing.
- **Private roadmaps and backlogs stripped.** benchmark.md's § Roadmap became § The stages
  (same B-numbered content — ROADMAP links by number and relies on it — minus the ordering claim
  and B0's landed-date). combat.md's C0–C5 became § Implementation map. § B-later became § Out of
  scope, rephrased as decisions with the condition that would reopen each.
- **Checks 10 (markers), 11 (backlog), 12 (statedoc)**, and `PLANNING` reworked so `design/*.md`
  is covered by living there rather than by being listed.

### Non-obvious calls

**Deleting a doc beats moving it when its live content is already someone else's.** The tempting
move was `PLAN.md` → `design/packaging.md`, keeping the set symmetrical. But a plan-of-record doc
has to own *design*, and packaging's design is settled and built: what remained was one
validation task, one deferred decision, and a set of rules that belong beside the installer.
A `design/packaging.md` would have been a file whose only purpose was to have somewhere to point.
ROADMAP's packaging track now says "no plan-of-record doc" explicitly, so the absence reads as a
decision rather than an omission.

**A design doc's status line is fine; its per-item markers are not.** combat.md still opens with
"built and shipped (0.3.0), mock-verified only" — that is a durable design fact a reader needs in
the first paragraph, and check 10 is written to allow it. What check 10 rejects is annotating
*individual items* with completion state, because that is the form that duplicates ROADMAP and
then drifts from it. The distinction is per-doc vs. per-item, not the word "done".

**"Out of scope" is design; "deferred" is a backlog.** BENCHMARK's § B-later mixed both — four
genuine scope boundaries and one piece of real work (regenerating the scripted player's digest)
that B1's own prereq depended on. The four stayed, rewritten as decisions with a reopening
condition; the fifth moved to `open-questions.md` on the benchmark track. Check 11 keys on
backlog-shaped headings (`Open decisions`, `Deferred`, `TODO`, …) and deliberately permits
"Out of scope", because a design doc *should* record what it refuses to do.

**The C-numbers were load-bearing in ~12 source comments.** Deleting COMBAT's C-phases would
have left `# ... (COMBAT.md C2)` pointing at nothing, which is the same defect in a new place.
They were mapped onto sections that exist (`C0` → § Tracker, `C1` → § The combat loop, `C2` →
§ Implementation map) rather than blanket-renamed.

**The B3 freeze was respected in substance, not just letter.** The reroute touched four files
that are technically model-facing assets, so it is worth recording *where*: a YAML comment inside
`dm-runner.md`'s `permission:` block (parsed config, never sent to the model), two TypeScript
header comments, and the `description:` frontmatter of `bench/assets/grader.md`. No craft prose
was altered and the golden-stream test is unchanged. A future round that wants to be strict about
the instrument should know the grader's description line moved.

**`findings.md` and `CHANGELOG.md` keep their dangling names on purpose.** Part 1's text still
says planning lives in four root docs, and the changelog still points at `BENCHMARK.md` for
0.4.0's design. Both are point-in-time records and retro-editing them is the failure the archive
exists to prevent — Part 1's header says so outright. Check 12 skips the two narrative docs for
the same reason: Part 1's *description* of a missing current-state doc is not a doc claiming to
be one, and the first version of the check flagged it.

## Declared lossiness / deferrals

- **COMBAT's C-phase "key resolutions" were compressed, not copied.** § Implementation map keeps
  the durable facts (advance-at-end and why opencode's missing execute-a-tool endpoint forces it;
  the `dm-runner` permission blocker that mock verification structurally could not catch; the
  repertoire living in apply-canon because it is capability-lineage; the bestiary-vs-NPC
  stat-block split) and drops the phase scaffolding, the per-phase Exit criteria, the
  "deferred to C5" pointers that C5 had already picked up, and the repeated
  "verified by dev/test_x.py" lines, consolidated into one. Git holds the originals.
- **`sessions/` → per-session directories is now on a track.** It sat in COMBAT § Open decisions
  as a real cross-cutting refactor nothing owned. It is `open-questions.md` § Canon layout plus
  ROADMAP docs 3, at high effort, explicitly never a rider on adjacent work.
- **Two COMBAT open-decisions were resolved, not moved.** Tracker serialization and HP
  roll-vs-average: the shipped engine serializes the documented shape and takes `hp` as a
  model-supplied param, so the question is answered in code — per CLAUDE.md's source-of-truth
  rule the doc got fixed (the state sketch is no longer labelled "serialization not locked").
  The AoE-queries and reaching-back-past-a-confirmed-combatant items were already marked settled
  inline, i.e. tombstones; they became plain design prose in § Tracker and § The combat loop.
- **Packaging Phase 1 closed as part of this round.** Every sub-item was already `[done]` except
  "document the terminal requirement, don't code it" — which this round did, in MAINTAINING
  § Portability. ROADMAP's "Phase 1 — in progress" row was inherited from a stale marker rather
  than from any outstanding work; it is deleted and § Landed carries it.
- **README/SPEC architecture overlap was resolved by SPEC's deletion**, so the question of
  deduplicating them does not need to be filed. README stays the 320-line user manual on
  purpose: the reference project's 60-line routing README works because that project ships
  nothing, and gm-llm ships a command people install.

## Green bar

`python -m compileall gm_llm` clean; all ten `dev/test_*.py` scripts pass; `tools/status.py
--check` and `tools/lint_docs.py` both clean. Checks 10–12 were verified against the
pre-surgery docs restored from `HEAD` into `design/`: **25 errors**, falling to 0 on the
consolidated set. A check that has never fired is decoration.

