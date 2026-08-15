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
| [3](#part-3--frontends-one-agent-driven-fight-loop-2026-07-27) | frontends | Why the *safer* of two duplicate loops becomes the shared implementation; where the agent-player seam sits for `PlayerSource` |
| [4](#part-4--frontends-one-session-loop-keyboard-or-agent-2026-07-27) | frontends | How a blocking loop and an async frontend are reconciled (and what must be released at shutdown); why a failed call is the frontend's call to answer, not the loop's |
| [5](#part-5--frontends-a-bench-run-is-a-lifecycle-2026-07-28) | frontends | Where to put a test seam so a harness fakes one step instead of a whole interface; why a green-across-the-board refactor still owes new tests |
| [6](#part-6--frontends-batch-chrome-and-an-inert-frontend-2026-07-29) | frontends | How a frontend attaches to something it must not perturb, and how that gets asserted rather than argued; why a parked question was the wrong question |
| [7](#part-7--benchmark-the-pilot-that-redirected-the-roadmap-2026-07-29) | benchmark | Why an instrument needs a content hash and not a version label; how to read a small batch honestly (t, not z; which subscores are noise); three claims that died to their own evidence |
| [8](#part-8--recalibration-the-ruleset-settled-and-why-prose-alone-cannot-land-it-2026-07-29) | recalibration | How a ruleset gets sorted onto the right axis; why "always loaded" means "loaded once", measured; a gate that examined a violation and passed it |
| [9](#part-9--recalibration-the-per-turn-brief-as-an-algorithm-the-runner-executes-2026-07-29) | recalibration | Why the fix for an ignored instruction is a *changing* line the orchestrator computes, not better wording; what handing a narrating agent a tool costs; making a prompt change measurable without a grader |
| [10](#part-10--direction-freezing-mimo-and-starting-luna-clean-2026-08-14) | direction | Why a concrete second product path must precede generic tier machinery; what "start over" preserves; why model reasoning is profile identity |

## Recurring threads (the classes worth knowing)

- **The first implementation is not a neutral abstraction.** The planned tier framework began by
  extracting MiMo's hard-coded stage graph into a playbook, then building every later tier through
  that shape. Once MiMo stopped being the target, this became a way to preserve its assumptions
  under generic names. The corrective pattern is a concrete second path first: preserve only the
  public outcomes and model-independent substrate, add the smallest seams the second path proves,
  and extract common machinery after two implementations reveal what is actually common. (Part 10)

- **Whatever measures needs an identity as much as whatever is measured.** A run's prompts were
  content-hashed; the rubric that scored it carried a hand-typed `v1` that did not move when the
  prose under it was rewritten in place, so two materially different instruments were
  indistinguishable and "which one scored this?" became git forensics. The class: any artifact that
  can be edited in place while keeping its label will eventually be, and a version string is a
  promise rather than a fact. `_FLOOR_RATE`, the dimension mapping and the dedup window are the
  same shape and still unversioned. (Part 7)
- **A gate that catches the flagrant case can be structurally blind to the worse one.** check-turn
  blocked an invented *named* antagonist and never saw an invented *unnamed* one that supplied the
  antagonist's cover identity — because the triage keys on "newly-named things" and the preamble
  waves through "mere addition". The blind spot is not a weaker version of the caught case; it is
  its complement, and a benchmark reading that instrument scores the blindness as quality. Ask what
  shape of violation a check *cannot* express, not just how well it does what it does. (Part 7)
  Part 8 read the gate's own verdict and found the mechanism was not blindness at all: the check
  examined the unnamed invention, classified it, and **passed** it as "consistent with the world".
  Hence the sharper rule — **before widening a check's net, read what it said.** "Didn't see it" and
  "saw it and approved it" look identical from the outside and have opposite fixes; only the second
  means the *criterion* is wrong, and widening intake against it changes nothing.
- **"Loaded" is not "in effect" — count the tool calls before tuning the prose.** Skills the corpus
  calls always-loaded are loaded exactly once, on turn 1, and never re-loaded across a 41-turn
  session, even though the per-turn brief names them every turn: the runner treats loading as a
  once-per-session act. Canon reads have the same shape — one mid-session lookup across five runs.
  The class: whenever compliance with an instruction *is* a tool call, it is directly observable, and
  a prompt round that tunes the wording without checking whether the call ever fires is tuning text
  the model stopped consulting. Reach for the session records first. (Part 8)
  Part 9 is the repair half, and it generalizes past prompts: **an instruction that reads the same
  every turn gets scored as already satisfied, so the fix is a line that changes, computed by the
  code that knows.** The wrap countdown had already learned this — a static "a few more turns" was
  deferred every turn until it became a descending number — and the staleness line is the same
  device on a different failure. Better wording is not the lever; state the model can't fabricate is.
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
- **When two copies of a loop differ, the difference is usually a safety property — unify
  toward it, not away from it.** autoplay's and bench's fight drivers differed only in whether
  a PC slot burned a turn against the cap; the shared `play_combat` took the counting version as
  the implementation and made "no cap" the argument. The general form: whichever copy holds the
  invariant is the base, and the laxer copy is a call site that opts out explicitly. (Part 3)
  Part 4 applied it once more and found the corollary: when the copies also disagree about a
  *case* neither documents — resuming into a live fight, which both agent-player loops got wrong
  — unifying is what surfaces it, because the merged loop has to answer the question once.
- **When a frontend attaches to something it must not perturb, enumerate what it may do — the
  answer is "almost nothing", and the test is a diff against the unattached run.** Batch chrome
  looked like a rendering problem and was a permissions problem: the useful question was not
  "what does cancel mean here" but "what is a frontend allowed to do to a run at all". The rule
  that fell out generalizes past bench: an affordance carries over only if its effect is
  *traceless* in whatever the system is measuring (ctrl+x leaves no turn behind, so it stays);
  everything else — a typed line, a wrap, even a read that costs a call — is refused. And once
  the answer is "nothing", it is assertable: play the same work watched and unwatched and require
  the records to match. (Part 6)
- **A thread parked on a UI is a thread that will not exit.** The blocking session loop runs on a
  worker thread and waits on the app's event loop to render; on shutdown Textual cancels the
  worker's *coroutine* while its thread keeps running, so any wait the thread is sitting on
  (the player source, combat's confirm gate) has to be released explicitly, and any hop back to
  the UI has to no-op once the app has stopped. Otherwise `asyncio.run` hangs joining its
  executor and the app never quits. The rule generalizes to every blocking-worker/async-frontend
  seam this repo adds. (Part 4)

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

# Part 3 — Frontends: one agent-driven fight loop (2026-07-27)

## The gap

`autoplay.py` and `bench/runner.py` each carried a private `_play_combat`: same shape (build a
`CombatDriver`, pump to a PC slot, prompt the `player` agent with `player_combat_turn` over the
latest beat, repeat until the fight ends), different in exactly one respect that mattered —
bench counted each PC slot against `turn_cap` so a fight could not make a run uncappable, and
autoplay counted nothing at all. Two copies of a loop that differ in a safety property is the
worst version of the duplication class: a fix to one is invisible in the other, and the *fact*
that they differ deliberately was recorded only in one of the two docstrings.

It is also the thing frontends 2 has to build on. `PlayerSource` collapses the out-of-combat
turn loop; if the in-combat loop is still forked at that point, the fork just moves.

## What the round does

Hoists both into `play_combat` in `orchestrator/combat.py`, immediately below `CombatDriver`, and
rewrites the two callers to be dialects of it. **The name is the old one minus its underscore**,
deliberately: a hoist that also renames costs grep continuity for no gain, and `combat.play_combat`
stuttering at a qualified call site nobody writes is not a reason. autoplay's surviving console
wrapper is `_console_combat`, so the two never sit an underscore apart.

- **`turn_cap=None` disables accounting; a number enables it.** Bench's semantics are the
  implementation, not a variant of it — the cap check, the pre-increment, the cap-return of the
  *last beat* rather than an exit narration, and the `(scene, turns, hit_cap)` triple all came
  over verbatim. Autoplay passes `turn_cap=None` and ignores the other two return values, which
  is honest about what it is: a mode that caps normal turns only. Doing it the other way round
  — autoplay's shape as the base, bench's counting as an add-on — would have made the
  load-bearing behavior the special case.
- **Three optional hooks carry the output dialect**, which is the whole of what differed
  besides accounting: `on_beat(narration, who)` (already the driver's own hook, so `play_combat`
  wraps it only to keep the "latest beat" cursor), `on_slot(event, turns)`, `on_player(text)`.
  Bench passes one, autoplay all three, and the hookless default is a silent fight. The cursor
  wrapping is why `on_beat` stays a pass-through rather than being folded away: an interface
  that returns a reaction from it still interjects, which is what makes this shareable with the
  TUI later rather than being an autoplay-only helper.
- **Placed in `combat.py`, not in either caller.** The module header already claimed to be the
  one home for combat sequencing policy while two interfaces kept their own copy of the loop
  around it; that header now says which layer each interface drives (the TUI drives
  `CombatDriver` directly because the human *is* the input source; the agent-player interfaces
  share `play_combat`).

**The armor was thin where the risk was.** `dev/test_bench.py` covered bench's path end to end
(natural close and cap breach, both through `run_once`), but nothing tested the function itself
and nothing at all tested autoplay's. Two scenarios were added to `dev/test_combat_driver.py`,
driving `play_combat` directly over the existing fake tracker backend: the uncapped call (hook
ordering, exit narration, one slot counted even with no cap) and the capped one (a fight still
live when the cap trips returns `hit_cap` with the last beat, and — the assertion that actually
catches a regression — consumes no further player prompt).

## Declared lossiness / deferrals

- **Autoplay now counts combat turns it does not use.** `play_combat` increments `turns` even
  when `turn_cap is None`, and autoplay discards the count. That is deliberate: one code path,
  no `if` around the accounting. If autoplay ever wants a combat-aware cap, the number is
  already there.
- **The console dialect is unchanged but no longer verified by a test.** Autoplay's `speaker`
  and `note` lines were preserved by inspection; the new tests assert hook *ordering* and
  payloads, not the console formatting. Nothing tests `gm_llm/autoplay.py`'s output today and
  this round did not open that.
- **`play_combat` is exported from `orchestrator/__init__.py`** on the same footing as
  `CombatDriver`. It is library surface now, so frontends 2 should extend it rather than wrap
  it — in particular, when `PlayerSource` lands, the `backend.prompt(...)` call inside it is the
  seam that becomes a source call.
- **The working tree carried Part 2's uncommitted reroute** when this round opened, though
  HANDOFF § Where things stand called it clean. Three of the files this round touched
  (`combat.py`, `runner.py`, `test_combat_driver.py`) already had unstaged edits, so this round's
  work could not simply be committed on its own as `design/frontends.md` § Sequence asked. It
  was untangled instead: this round's hunks were reverse-applied to reconstruct Part 2's tree,
  which was verified green on its own and committed first, then this round's work was restored
  on top. **The lesson is Part 2's, not this round's** — "green gate" and "committed" are
  different claims, and only one of them the gate can check.
- **The loop was then changed to stop it recurring**, per the method's own rule that a cleanup
  is a missing check rather than a chore. `/close-round` § 6 said "commit only if Karl asked",
  which is exactly how a closed round could sit uncommitted; it now says that closing a round
  *is* committing, that anything needing Karl's decision is raised **instead of** closing rather
  than alongside it, and how to untangle a tree carrying a previous round's work. `CLAUDE.md`
  § Standing rules carries the carve-out from the standing commit-only-when-asked rule, because
  that is where that rule lives — the skill points at it rather than restating it.

## Green bar

`python -m compileall gm_llm` clean; all ten `dev/test_*.py` scripts pass, including the two new
`play_combat` scenarios; `tools/status.py --check` and `tools/lint_docs.py` both clean (0 errors,
0 warnings). No model-facing prose changed, so the B3 freeze is untouched.

# Part 4 — Frontends: one session loop, keyboard or agent (2026-07-27)

## The gap

Three interfaces, three turn loops. `bench/runner.py` and `autoplay.py` each ran a push-driven
`for`/`while` around `backend.prompt(player_sid, …)` → `game.turn(…)` → render; `tui/app.py` ran
the same sequence inside out, idling in `on_input_submitted` and spawning a worker per turn. The
grid's empty cell followed from that: `--player auto --ui tui` exited with a message saying so,
because feeding the TUI a player agent meant giving a pull-driven frontend a push-driven loop.

The duplication was not only structural. The bracketed heading that hands the player agent its
character packet was spelled out in both agent-driven callers, verbatim, one edit away from
drifting — and the *cases* differed silently: bench counted combat slots against the cap and
autoplay did not; neither could resume into a live fight (both would send a normal turn into a
live tracker); a cancelled turn in the TUI was handled by one code path per call site.

## What the round does

Adds `orchestrator/play.py` — `PlayerSource`, `PlayHooks`, `PlayResult`, `play_session` — and
rewrites all three interfaces as dialects of it. `play_combat` (Part 3) takes the same source and
hooks, so a fight is the same code whether a human or an agent answers the PC slot.

- **The axis is where the next message comes from, and nothing else.** `AgentPlayer` prompts the
  `player` agent (and owns the packet/story priming, now stated once); `KeyboardPlayer` parks the
  loop's thread until a frontend calls `submit(text)`. `human` on the source is a *rendering*
  flag — the TUI frees its input box for one and shows "the player is thinking" for the other —
  never a policy fork inside the loop.
- **The loop keeps only what is genuinely shared.** Opening a session (resume-or-start, with
  bench's archive continuation and the TUI's phases) and the post-session tail (handoff notes,
  reconcile) stay with the callers, because that is where they really differ. What moved in is
  what was being copied: cap accounting, the combat handoff, the wrap signal, the priming.
- **A fight is entered from the top of the loop**, not from the turn that started it. That one
  placement is what fixes resume-into-combat for every interface at once: any pass that finds
  `game.in_combat` fights. Both agent-player callers were previously wrong here and neither had
  a test that could have noticed.
- **`on_interrupt(stage, exc, message) -> bool` is the frontend's answer to a call that raised.**
  With no hook (autoplay, bench) a `BackendError` propagates untouched, which is exactly what an
  unattended run needs to record a rate-limit give-up. The TUI's hook reverts the runner session,
  hands the message back and returns True — so a cancel or a give-up costs a turn, not a session.
  The one exception is a hard failure *inside a fight*: re-entering combat goes straight back to
  the model with no human gate, so that ends the loop rather than grinding against a dead backend.
- **An interrupted turn costs no turn against the cap.** The loop restores the turn count it
  entered the iteration with. A cancelled turn leaves no trace in the transcript, canon or the
  archive; a cap it silently burned would have been the only trace it left.
- **`--player auto --ui tui` is now a source swap**, wired end to end: `Lifecycle.player_source()`
  resolves the axis (one fresh source per session — a stopped `KeyboardPlayer` never wakes, and a
  new `AgentPlayer` session re-primes the packet), `--turn-cap` bounds the run, and the character
  packet is resolved by the same `autoplay.read_character` the console mode uses.
- **`stop()` is on the source base class, and it is graceful.** It was nearly a `KeyboardPlayer`
  detail, which would have left a watched run with no way to end: the TUI is *always* busy during
  one, so `ctrl+w` would have had nothing to act on. Stopping lands at the next ask, so the turn
  in flight finishes and is kept — throwing away a half-played turn is never what a wrap wants —
  and `action_wrap` gains its one carve-out from "no-op while busy" for exactly that case.

**The TUI was the risk, so it got an oracle.** `dev/test_tui_loop.py` drives the real `PlayApp`
headlessly through Textual's own pilot over `MockLifecycle` — a whole session (typed turns, a
fight with its confirm gate and an interjection, the runner's close, the wrap, the next session on
a fresh loop) and a cancel-and-carry-on. It paid for itself immediately: it caught a shutdown
deadlock (below). `dev/test_play_session.py` covers the loop headlessly — priming, hook order and
numbering, the cap, a threaded `KeyboardPlayer`, the combat handoff, resume-into-combat, and both
interrupt policies. The mock grew a `pace` multiplier so the scripted delays that make it watchable
cost the suite nothing.

**The bench suite is the regression armor that mattered most** and it needed no changes: all
sixteen cases — natural close, cap breach, combat entry and mid-fight cap, the rate-limit turn
count, both resume paths — pass against the shared loop unmodified. Bench keeps its exact turn
accounting through `on_player`, which fires with the number of the turn about to be drafted, since
an exception carries no return value.

## Declared lossiness / deferrals

- **Console autoplay's cap now covers combat slots.** Part 3 recorded the old behavior as
  deliberate ("caps normal turns only"); one loop cannot hold two cap policies, and the choice
  between them is not close — an endless fight in an unattended run is precisely what a safety net
  is for. This is the Part 3 rule applied again: unify toward the invariant.
- **A cancel inside a fight forgets the slots played since the fight began**, for cap purposes:
  `play_combat`'s count rides on its return value, which an exception skips. Inert where cancel
  exists (the human frontend is uncapped) and documented at the loop.
- **A turn that both wraps the session and starts a fight is read as a wrap.** No runner should
  produce that draft; of the two readings, opening a fight into a session that has just ended is
  the worse one.
- **The shutdown deadlock was real, and predated the round in miniature.** On the way out Textual
  cancels a worker's coroutine while its thread keeps running, so the TUI's `_loop_live` flag went
  False with the thread still parked on the player source — and a parked pool thread keeps
  `asyncio.run` from joining the executor, hanging the process at exit. The fix is a rule, not a
  patch: `_stop_session` releases *everything* the worker can park on (source and confirm gate)
  regardless of how live the loop looks, and every hook hops to the UI through `_ui`, which
  no-ops once the app has stopped. The old per-turn workers had the same hazard in a smaller
  window; nothing would have found it without the pilot test.
- **The TUI's own `--player auto` cell has never run against a live model.** It is mock-verified
  like everything else here, and it inherits the live shakedown debt already parked on ROADMAP
  track **live**.
- **`_character` (bench) and `read_character` (autoplay) are still two resolvers.** They agree on
  handling and now feed one `AgentPlayer`, but where the packet lives and how it is generated is
  benchmark B1's open player-end contract, not this round's to settle.

## Green bar

`python -m compileall gm_llm` clean; all twelve `dev/test_*.py` scripts pass, including the two
new ones (`test_play_session.py`, `test_tui_loop.py` — the TUI pilot runs in ~7s at `pace=0`);
`tools/status.py --check` and `tools/lint_docs.py` both clean. No model-facing prose changed: the
packet framing moved home byte-for-byte and the prompt fingerprint over the run dirs is unaffected,
so the B3 freeze is untouched.

# Part 5 — Frontends: a bench run is a lifecycle (2026-07-28)

## The gap

Step 2 gave the three interfaces one turn loop, but left the *session* around that loop wired
twice. `Lifecycle` is the object the TUI is written against — it owns the `Game`, resolves the
`--player` axis, and its `wrap()` is the whole post-wrap tail behind one `on_stage` protocol.
`bench.runner.run_once` re-did all three by hand: `Game(backend, gate_factory(...))`, a
`backend.create_session("bench-player")` fed to a locally-built `AgentPlayer`, and an injected
`reconcile_fn(backend, gate, logs, n)` reached through a *second* `gate_factory` call. The
consequence was not a missing feature but a missing seam: a bench run produced no stage events
anyone could render, so "watch a batch reconcile in the TUI" had nothing to attach to.

## What the round does

`run_once` builds one `Lifecycle` and plays it. `Game` and `AgentPlayer` leave bench's imports
entirely; the tail is `lifecycle.wrap(on_stage=…)`.

- **The injected seam moved up, not away.** `reconcile_fn` is replaced by `lifecycle_factory`,
  defaulting to `_default_lifecycle` (which is one `Lifecycle(..., player="auto")` call). The
  expensive step inside it is now `Lifecycle.reconcile(n, on_stage, commit)` — one line lifted
  out of `wrap` so a harness can stand in for *it* rather than for the whole lifecycle. The test
  fake is a three-line `Lifecycle` subclass, so `Game`, the player source and the warm-runner
  handoff stay real in every bench test instead of being mocked alongside the reconciler.
- **The gate is built once.** `_post_wrap` used to call `gate_factory` a second time to hand a
  reconciler its gate; the lifecycle already holds the one the game plays under.
- **`--play-only` is `handoff()` without `wrap()`.** The alternative — a `reconcile=False` flag on
  `wrap` — would have pushed a bench-shaped axis into the product interface for no other caller.
- **The stage protocol is live in bench today.** `_post_wrap` passes `on_stage=lambda key:
  note(f"reconcile: {key}…")`, so a console batch already narrates `handoff → digest → … →
  propagation` instead of sitting silent through the longest part of a run. Step 4 swaps that
  `note` for the TUI's ticker and nothing else.

## Two tests for the contract, not the plumbing

The sixteen existing cases passed unmodified once the fakes were re-pointed — the armor HANDOFF
named, doing its job. Two new ones pin what the round is *for*, since a refactor that keeps every
old test green proves only that it changed nothing observable:

- `test_post_wrap_is_lifecycle_wrap` — the tail really is `wrap()`: the warm runner's
  `session-1-notes.md` lands, and the stage ticks reach the run's progress notes.
- `test_player_source_comes_from_the_lifecycle` — the fixture's packet primes the player agent's
  *first* message and only that one, observed at the backend rather than asserted about the
  wiring. Nothing tested the packet actually reaching the model before.

## Declared lossiness / deferrals

- **The autoplayer's opencode session is titled `play-player`, not `bench-player`.** One name for
  the scripted player across every mode is the point of routing through `player_source()`; the
  title is a debugging label, and bench's own log line still prints the id.
- **`wrap()` rolls the lifecycle on to session N+1, which bench never plays** — one wasted
  `create_session` per run, immediately before `backend.stop()`. Paying it keeps `wrap` a single
  contract for both callers; a `roll=False` flag would be a bench-shaped hole in the interface.
- **A fixture with no session plan now fails loudly** (`ValueError` from `run_once`) instead of
  playing a `Game` with `session=None` and writing nothing. It sinks the batch, which is right: a
  misassembled fixture fails identically on every run.
- **Console autoplay is still the one direct `Game` construction.** It is now the whole of
  frontends step 5, parked on ROADMAP. It blocks no cell — the TUI's auto mode already runs on
  the real lifecycle — and routing it needs `player_source()` to carry the resume story an
  `AgentPlayer` primes with, which is a contract question rather than a wiring one.
- **Comparability is untouched and still unenforced.** No archive-facing code changed and no
  condition field moved, so the B3 freeze holds; the open question about whether the "a frontend
  never touches the archive path" invariant should be *asserted* rather than argued is unchanged.

## Green bar

`python -m compileall gm_llm` clean; all twelve `dev/test_*.py` scripts pass (bench now 18/18);
`tools/status.py --check` and `tools/lint_docs.py` both clean. No model-facing prose changed.

# Part 6 — Frontends: batch chrome, and an inert frontend (2026-07-29)

## The gap

Steps 1–3 made a bench run renderable — one turn loop, one `PlayHooks`, one `Lifecycle` with a
stage protocol behind it. Nothing rendered it, because a *batch* is not a session: `PlayApp`
took its lifecycle in the constructor and read `self.lc` for the app's whole life, and N run
dirs are N lifecycles. The blocker was the app's shape, not the loop's.

And the question the plan of record parked first — what `ctrl+x` means for a batch — turned out
to be the wrong question, or rather a question whose answer falls out of a bigger one that had
been sitting in the backlog unanswered: **what is a frontend allowed to do to a run at all?**

## The decision: watching is read-only

`ctrl+x` needs no new meaning. In a live session it aborts the call in flight and the loop asks
again from the same scene — "redo this call", not "end anything" — and a cancelled turn provably
leaves no trace in transcript, canon or archive (the loop rolls `turns` back to its checkpoint;
the app reverts the runner session). That reading transfers to a batch verbatim, so it stays.

What has no reading is everything *else* a frontend could do, and the answer is that it may do
none of it, because bench's value is condition-stamped runs that pool:

- **A typed line is refused.** It would be a turn (or a meta call) that the archive cannot
  distinguish from the run's own, and the run would stop being comparable to a headless one.
- **`ctrl+w` is refused.** A wrap from the frontend ends play early; `play_session` would return
  `stopped`, which `run_once` — before this round — read as a cap and stamped a `cap` event for.
  The run would have archived a ceiling it never hit. That was a live bug the chrome exposed:
  `stopped` is now its own branch, recorded `incomplete: stopped from the frontend`, no `cap`
  event, classifying `resumable`.
- **The context-usage readout is skipped.** It is a real per-turn backend call that a headless
  run does not make.
- **The loop's error policy stays bench's.** `BatchHooks` composes the frontend's `PlayHooks`
  *under* bench's own bookkeeping rather than replacing them, and consults the frontend's
  `on_interrupt` only for a `BackendCancelled` — the cancel above. Every other give-up rides out
  to the record exactly as it does headless, so a watched run gives up where an unwatched one
  does.

This also settles the *other* frontends open question, which had been getting weaker on the
argument "the frontend never touches the archive path, but nothing enforces it". Something
enforces it now (below), so `ui` stays out of `conditions` — stamping it would fragment the
baseline B3 is meant to bank, and there is nothing left for it to explain.

## What the round does

- **`bench.runner.BatchHooks`** — the batch's side of a frontend: `on_run(index, total, run_id)`,
  `on_open(lifecycle, source, scene) -> PlayHooks`, `on_stage(key)`, `on_close(record)`. Threaded
  through `run_once`, `run_batch` and `_resume_batch`, defaulting to silence. `run_batch` stays
  above the frontend — per-run backends, conditions stamping, the manifest, resume classification
  are none of them per-session.
- **`PlayApp` attaches a lifecycle per run.** `self.lc` is None between runs; a new `phase`
  property answers for it (nothing but a real campaign is ever in setup). `on_open` runs on the
  batch thread: it latches the lifecycle and the run's *own* source (two sources would be two
  players), wires the retry notice and the step ticker, starts the stream tap, and hands back
  `_session_hooks()` — the same hooks a keyboard session renders through.
- **`BatchHeader`** — run *k* of *N* and the outcome tally, which no per-session widget can say
  because the batch outlives every lifecycle the app attaches.
- **`bench run --ui tui`.** `--stream` is dropped there (the pane is the stream).
- **The batch is a plain thread, not a Textual worker.** The CLI joins it *after* `app.run()`
  returns, so the run in flight finishes unwinding — backend stopped, manifest line written —
  instead of being abandoned mid-record when the screen closes. A frontend that goes down ends
  the batch there and leaves the rest to `--resume`.

## The test is the invariant

`dev/test_bench_tui.py` plays the same fixture twice over the same fakes — once headless, once
through the real `PlayApp` on Textual's pilot — and requires the two batches' outcomes, turn
counts and **archive event streams to be identical**, typing a line into the watching app on the
way past. The second scenario quits mid-run and pins the honest ending: `incomplete`, no `cap`
event, `classify_archive` says `resumable`, run 2 never opens, the manifest line is on disk.

That is the comparability constraint moved from prose into the gate. It is worth noting what
makes it cheap: the assertion is possible only because the archive is written by one path that
neither frontend can reach.

## Declared lossiness / deferrals

- **No context-usage readout while watching a batch** (above). The subtitle just says the mode.
  If it is ever wanted, the honest version reads the archive, not the backend.
- **The watched run does open one extra connection** — the behind-the-screen `EventTap`, an SSE
  subscription to opencode's own event bus. It is the same read-only tap `bench run --stream`
  makes and it emits nothing into the run; the archive equality test covers the claim.
- **`--player auto` in a live campaign could always have crashed on a typed line** (`AgentPlayer`
  has no `submit`). Found while guarding the batch path; fixed there too, as a notice.
- **Console autoplay is still the one direct `Game` construction** — frontends step 5, unchanged
  and blocking nothing.

## Green bar

`python -m compileall gm_llm` clean; all thirteen `dev/test_*.py` scripts pass;
`tools/status.py --check` and `tools/lint_docs.py` both clean. No model-facing prose changed.

# Part 7 — Benchmark: the pilot that redirected the roadmap (2026-07-29)

## The gap

Five identical-condition tier-`low` runs sat in `bench-out/` ungraded-in-part and unread. The
round set out to answer one question — is five runs enough to bank as B3's baseline? — and the
answer turned out to invalidate the question. Three separate things were wrong underneath it:

- **The grading instrument had no identity.** A grades file recorded `rubric: v1`, a hand-typed
  label. `rubric-v1.md` had already been rewritten in place (penalty table, binding categories,
  wider dedup window) with every grades file on both sides still reading `v1`. Establishing which
  instrument had scored a given run took wall-clock timestamps cross-referenced against `git log`.
  The prompts a *run* played were content-hashed; the instrument that *scored* it was not.
- **The report claimed precision it did not have.** No error bar at all, and the sample-size
  arithmetic done by hand in-session used the normal `1.96` — right when the spread is known,
  wrong when it is estimated from the same five runs being averaged. It understated the interval
  by 42%.
- **The prompts disagreed with the design intent** in ways no run could surface, because the
  checker cannot see what it is not told to look for.

## What the round does

**Fingerprints the grading instrument** (`grade.instrument_fingerprint`, committed `ddcb3d6`): a
content hash over `bench/assets/` stamped into every grades header, mirroring
`runner.prompt_fingerprint`. The idempotence check compares it, so sharpening a rubric under the
same label now re-grades instead of silently skipping; `bench report` flags a batch scored by more
than one instrument the way it already flags mixed play conditions. Pre-fingerprint headers are
**grandfathered**, not invalidated — the same call `_condition_signature` makes for pre-fingerprint
archives, and re-scoring a banked batch is worse than leaving history readable.

**Puts an error bar on the score.** `mean_ci95` and `resolution95` in `scoring.py`, rendered under
the INTEGRITY SCORE line. Student's t, from a table, because the batch estimates its own spread
from the runs it is averaging: `t(4)=2.776`, not `1.960`. The batch reads **42.8 ± 16.9 (n=5)**,
and two batches of five could only separate a ~27-point difference.

**Marks thin dimensions instead of printing false precision.** Under ten violations batch-wide, a
dimension subscore is a handful of severity labels — and labels reproduce at ~80% across passes,
with disagreement averaging out only as 1/√(findings): ~20% of the subtotal over 5 findings, ~6%
over 15. The composite pools 13–22 and survives; "mechanical integrity 98.9" over *one* violation
does not.

**Writes the pilot up** (`dev/fixtures/hollowfell/pilot-2026-07-29.md`) as a variance pilot, never
a baseline — the fixture's own `fixture.json` says not to bank against it.

**Opens track `recalibration`** and `design/runner-authority.md` with it: a runner-authority model
(planned content binding; improvisation licensed by the *player*, not the runner; never
arc-impacting lore; never unauthorized revelation) plus the four places the prompts diverge from
it. **Inverts the standing sync rule** in the process — "nothing model-facing before B3" was sound
while the prompts were believed correct and backwards once they are not, because baselining
prompts about to be rewritten measures a system that will not exist.

### The reasoning worth keeping

**Three claims died in this round, each to evidence rather than argument**, and the sequence is the
real finding: a measurement round's job is to survive its own results.

1. *"Cross-day grader agreement fell to 67%, so the model may drift."* Two pairs shared a pass; the
   third (80%, also cross-day) was never computed. 67/80/87 across three pairs of 15 is one rate
   near 78% plus binomial noise. **Compute every pair before naming a mechanism.**
2. *"The composite absorbed the label churn."* Penalty moved 35.25 → 35.50 across two passes, which
   looked like robustness and was arithmetic luck: −8 from a critical→major cancelling +9 from
   three minor→major. Four of five re-labellings went *up*. **A near-zero net is not evidence of
   cancellation until you decompose it.**
3. *"Session-length variance is the highest-leverage thing to fix."* The 7-turn run reached the
   plan's centrepiece; the 29-turn run never did, and `session-3-plan.md` § Pacing & Exits
   sanctions both exits. **Read the artifact before calling its variation a defect.**

**The instrument's blind spot found the roadmap's.** `5c16` invented two things: "Aldric Voss", a
*named* antagonist identity — check-turn's check 4 fired and the grader scored it the batch's most
severe finding — and "a geologist, sent by the consortium, three months ago", spoken by a canon NPC,
appearing nowhere in canon or plan, supplying the antagonist's cover identity. Nothing flagged the
second. The difference is not consequence; it is that check 4 triages "the draft's newly-named
things" and an unnamed actor never enters the triage, after which the preamble's *"never flag mere
addition"* covers it. **A checker that catches the flagrant case can be structurally blind to the
worse one**, and a benchmark measuring a system that way scores the blindness as quality.

**Detection is the floor, not the goal** (`runner-authority.md` § Delivery). The runner will not
load a skill or read a file unless told to on that turn — which is why `turn-reminder` exists, and
the stronger form of `CLAUDE.md`'s "a universal rule parked in an unloaded skill is silently absent"
is that *loading is not salience*. But teaching the checker to complain raises the violation count
and improves nothing: gm-llm is a game as well as a benchmark, and a corrected draft costs a real
turn. Each gap has two halves — make it visible, then make it unnecessary.

## Declared lossiness / deferrals

- **The runner-authority model is provisional.** Transcribed from one conversation, not worked
  through section by section, and the gap table is what a single pilot exposed rather than an
  audit. Both passes are owed before any prose is authored — ROADMAP `recalibration` row 0, and
  the doc says so in its own § The model is provisional.
- **Four grade headers carry a *backfilled* instrument hash**, asserted from git (graded
  2026-07-29T07:56–08:20Z, after the last `bench/assets` change at 2026-07-28T05:49Z, tree
  unmodified since) rather than observed at grade time. Each carries an `instrument_backfill` field
  saying so. `5c16` was re-graded fresh instead; its superseded grades are parked under
  `superseded-20260726/` and are what gave finding 3 three passes of one run to work with.
- **`bench grade --double --sample N` grades `findings[:N]`** — the first N, not a random N — so the
  pooled 92%/88% agreement over-represents early turns. Making it random changes the instrument, so
  it was not done in passing.
- **The pilot's scores do not survive recalibration**; its methodology findings do. The prompt
  fingerprint is part of a run's condition, so this is visible rather than silent.
- **Plan coverage is unmeasured and stays that way this round.** A run that never reaches the plan's
  centrepiece breaks no authority rule — the content it played was all planned — and nothing sees
  it. Parked in `runner-authority.md` § What this does not settle.
- **`--sample`'s bias, the floor calibration, and the words-vs-units denominator** are all carried
  to B3 rather than decided on five runs.

## Green bar

`python -m compileall gm_llm` clean; all thirteen `dev/test_*.py` scripts pass (`test_grade.py` now
21, six added this round); `tools/status.py --check` and `tools/lint_docs.py` both clean. **No
model-facing prose changed** — the recalibration it sets up is entirely future work.

---

# Part 8 — Recalibration: the ruleset settled, and why prose alone cannot land it (2026-07-29)

## The gap

Part 7 opened track **recalibration** on a model of runner authority transcribed from a single
conversation, plus a four-row gap table produced by reading the runtime gate. Both were explicitly
provisional: the model had never been worked through, and the gap table was what one pilot happened
to expose rather than an audit. Nothing could be authored against either.

Two things were wrong with them in ways only the work could show. The model's rules were sorted on
the wrong axis in one place and carried a carve-out that licensed the exact failure it was written
to stop. And the gap table was written against the **checker**, so it found checker gaps — it never
asked what the *runner* is told, which turned out to be nothing at all.

## What the round does

### The ruleset — eight rules to six

Settled section by section with Karl. `design/runner-authority.md` § The model now holds the six,
and § What the settling changed records the three substantive moves so a reader who meets the
eight-rule form quoted in Part 7 is not misled:

- **"Nothing that outlives the session" was scoped wrong.** Duration is not the boundary: a crate of
  rations, a guard with a name and a grudge, and a nameless miner all outlive the session and are all
  permitted. **Story impact is the boundary.** Three separate prohibitions collapse into one rule —
  *what you invent may complicate the character, never the plot* — expressed in objects the system
  actually has (arc, thread, clock, live investigation) rather than in a judgment about "substantial
  consequence".
- **The staged-NPC carve-out is cut.** The transcribed rule permitted revelation "by an NPC the plan
  staged", which reads as licensing whatever a staged NPC says — and the geologist was delivered
  through a staged NPC. Staging authorizes the NPC, not their content. Their dialogue is governed by
  the same rule as anything else, which makes the four-case set fall out cleanly: "I don't know" —
  fine; the same line while lying — fine, it comes from the plan's concealed tells; the foreman's
  lunch — fine; an investigation lead invented on the spot — blocked.
- **One rule was added, and it is the only one in the set that says yes.** *The plan fixes what can
  be learned, not the only route to it* — if the player bypasses the intended source, a plausible
  alternative route to the same fact may work. It reframes the whole problem: every other rule
  answers "what may I invent off-plan?", and this one says the question is usually wrong, because
  the answer is *relocate*, which requires authoring nothing. Its three limits were all found by
  Karl rejecting the first draft, and each closes a real failure: plausibility (no finding a
  foreman's opinions in a library), last-resort (no strewing leads), and **never move an NPC, a
  place, or an object** — because "move the beat" reads to a light model as *move the object*, and a
  teleported NPC is a worse failure than the omission it fixes.
- **Closing early was demoted** from the response to divergence to the response to *exhaustion*. The
  earlier form let a runner spend twenty turns on individually-harmless scenes and stay compliant,
  which is the pilot's failure mode exactly. Inconsequential scenes are the walk to the exit, never a
  way to keep playing.

### The audit — the runner is told none of it

Ten prompts read section by section. The finding is not disagreement but **absence**: the
runner-facing path (`dm-runner`, `session-run`, `session-flow`, `social-play`, `discoveries`,
`turn-reminder`, `runner-header`) states none of rules 1–4. `session-run`'s own section titled
**"Table craft — non-negotiable"** carries four bullets, all governing runner-vs-player; not one
governs runner-vs-canon. Where the prompts do speak they lean the other way: `dm-runner` names
improvisation as one of four pillars of the job, and `session-plan` instructs the planner to leave a
30–40% improv budget.

Two inversions are worth carrying forward. `discoveries` binds the plan on its **mechanical** flag
(check-gated vs. player-assembled) — the axis the settled rule 1 makes *advisory* — while nothing
binds the runner to the committed answer the planner was required to fix. And `check-conduct`'s
biggest catch by volume is player agency: the boundary the corpus states well is the boundary the
gate spends itself enforcing.

### The checker approved the geologist

Part 7 recorded that nothing flagged the invented geologist and inferred the cause was check 4's
newly-*named* intake filter. The archive says otherwise, and the correction matters because it
changes the fix. `check-turn` examined the turn and passed it — in writing:

> The geologist is a **legitimate new entity introduced through NPC testimony** — a natural response
> to the player's question about unusual visitors, **consistent with the world**… **The geologist
> should be registered in the INDEX post-session.**

It passed on precisely the two rules this round cut: *consistency, not obedience* and the staged-NPC
carve-out. In the same breath it computed that the thing needs a canon file — the predicate that
should have blocked it — and drew the opposite conclusion. The next turn it blocked "Aldric Voss"
stating its operative distinction outright (*"established in the transcript… but never named"*).

So the defect is the **classification criterion**, not the intake: the checker asks *does this
conflict?* where the rule asks *does this touch the plot?* Widening intake alone would have changed
nothing on this turn. It also disposes of an objection raised against putting "would this need a
canon file?" in front of the runner — that it has no reason to know the registration rules. The same
model volunteered that predicate unprompted.

### Why prose alone cannot land any of it

The strongest result of the round, and it is measured rather than argued. Counted from the five
pilot runs' opencode session records across roughly 125 runner turns: `session-run`, `session-flow`
and `discoveries` are loaded at **turn 1** in every run and **never re-loaded, in any run**. Canon
`read`/`glob` calls are all at turn 1 plus one `glob` near the close; there is exactly one
mid-session lookup across all five runs. The runner's own `dice` tool fires six times, total.

This kills the intuition it replaces. `discoveries` is not unloaded — it is read on turn 1 of a
session that runs to turn 41 and then sits forty turns back in context while the investigation it
governs happens. `turn-reminder` names it every single turn, and after turn 1 the runner treats the
instruction as satisfied: **loading is a once-per-session act.** "Always loaded" therefore means
"loaded once", and `session-run` is on the same footing as the companions the corpus treats as
optional. Only `turn-reminder` has genuine per-turn presence, and invention is substantially a
*staleness* problem that no prompt rule addresses.

That reorders the track. Making the reminder an executable algorithm — `dm-runner` is the only agent
in the corpus without `todowrite`, while `dm` and `narrative-checker` both have it and both use it
heavily — now runs **before** the rows that author rule prose, because it decides whether those rules
can live in skills at all. If loading becomes reliable the reminder gets *shorter*, not longer.

### Also

- Karl's stashed prompt trims were restored and are part of this commit — including the
  `session-flow` line that stops telling the runner someone downstream reconciles what it improvised,
  which is a rule-6 change the ruleset conversation arrived at independently. The stash's
  `check-conduct` hunk was **not** restored: it edits the "wrapping too early" bullet the same
  conversation decided to delete, and committing an edit to text agreed to be removed is noise.
- A standing criterion the audit adopted: **an agent is told about machinery only where recognizing
  it changes its behavior.** The `<turn-reminder>` tags stay (the runner must not echo what it does
  not recognize); "the orchestrator runs you" goes.

## Declared lossiness / deferrals

- **The prose rows are not started.** Row 0's job was findings; every authored change is rows 1–5.
  The audit's secondary divergences are recorded in the plan of record rather than fixed.
- **The planner-side audit is owed.** `npc-plan` commits disposition, agenda, what they know and
  concealed tells per NPC, and every trait it commits is one the runner cannot invent — but whether
  that block is rich enough was not read closely. It is row 5.
- **`check-conduct`'s "wrapping too early" bullet is decided-dropped, not dropped.** The decision is
  recorded; the deletion belongs to a row that authors prose.
- **Rule 3 has no home yet.** `discoveries` owns how information is found and `session-flow` owns the
  session's shape; routing is genuinely both, and splitting it invites the restatement rot. Deferred
  to row 1, which reworks the skill division.
- **Nothing was verified against a score.** No baseline is banked and the pilot's is superseded. But
  row 1 is the first change in the track measurable *without* the grader — skill loads and
  mid-session reads are deterministic observations in opencode's session DB.

## Green bar

`python -m compileall gm_llm` clean; all thirteen `dev/test_*.py` scripts pass; `tools/status.py
--check` and `tools/lint_docs.py` both clean. Model-facing prose changed only by restoring Karl's
stash — no rule authored this round.

# Part 9 — Recalibration: the per-turn brief as an algorithm the runner executes (2026-07-29)

## The gap

Part 8 measured the thing that makes prompt work futile: across five pilot runs the runner loaded
`session-run`, `session-flow` and `discoveries` at **turn 1** and never re-loaded any of them, in
sessions that ran past turn 40; canon reads were all at turn 1 plus one glob near the close, with
**one** mid-session lookup across all five runs. `turn-reminder` names the scene skills on every
single turn, so this is not an unread instruction — it is an instruction the model scores as
*already satisfied*. By turn 24 the campaign is being narrated from a memory of files twenty-three
turns back, which is where invented facts come from, and no rule written into a skill can reach
that turn.

So this row ran before the rows that author rule prose: it decides whether a rule can live in a
skill at all.

## What the round does

### The brief is a list, not a paragraph

`dm-runner` gets `todowrite` — it was the only agent in the corpus without it, while `dm` and
`narrative-checker` both have it and both work through it. The brief now opens each turn by asking
for a five-entry list built from its own step headings, and the steps were re-cut so **loading has
its own step**. It had been the first half of the old step 4, sharing a bullet with "then write the
world's response" — the enumeration ran straight into the narration instruction, which is a good
way to be read as preamble to it.

Two smaller calls inside the brief, both about the same failure:

- **The blank in step 2 ("Beat is ___") is filled by the model.** Writing the list is then an act of
  classification rather than a ritual, and classifying the beat is the whole trigger for which skill
  to load.
- **"Don't touch the list again once you start writing."** Not tidiness: opencode splits a turn at
  each tool call and returns only the last assistant message, so a runner that narrates and *then*
  marks its list complete hands back an empty draft. See the guard below — the instruction reduces
  the case, the code removes it.

### The staleness count is orchestrator-side, and that is the point

The load-bearing part of this round is not the list. A brief that says "load again, every turn" is
still a standing instruction, which is the exact failure class being fixed — the same static text
has ridden every turn since the pivot. So the orchestrator counts, off each turn's tool calls, how
many consecutive turns the runner has gone without calling `skill`/`read`/`grep`/`glob`, and past
five it prepends a line that says so **with the count in it**, which keeps climbing while it is
ignored.

This is deliberately the same shape as `_wrap_banner`, and for the recorded reason: the wrap nudge
was made a descending countdown because the runner read the same "a few more turns" every turn and
deferred every time. A line that changes is read; a line that does not becomes furniture. The
threshold is five — a scene skill is ~700 tokens and a session is context-bound, so re-reading is
not free, and five puts the campaign back in front of the runner several times a session without
paying for it every turn. Combat beats do not reach the counter (they run through `_run_gate`
directly), so a fight freezes it rather than firing a line that would point the runner at the wrong
craft.

`runner-header` was amended in the same spirit. It opened with *"read for you; you need not re-open
these"* — literally true at turn 1 and licensing the failure at turn 24. It now says the head start
has a shelf life.

### The guard the task list makes necessary

Giving the runner a tool it will call *while narrating* creates a way to lose the narration.
`_run_prompt` read text from the POST response, which is only the last assistant message; prose
written before a trailing tool call was invisible, and `_run_prompt` would then classify the turn as
a legitimate tool-only reply and return `""` — an empty draft, gated and appended to the transcript
as a blank scene. It now recovers the turn's text from session history before reaching that
conclusion. The scan `_recent_tool_calls` already did was generalized to `_recent_parts`, so both
readers share one history fetch.

This hazard predates the round (the runner could already end a turn on `task_complete`); handing it
a per-turn tool is what made it likely enough to fix.

### Measurement without the grader

Each archived turn now carries `tools` (what the runner called while drafting) and `stale` (turns it
had then gone without opening anything). The pilot derived this from opencode's own session DB by
hand; it is now a read of `bench-out/`. Whether this round took is exactly the question those two
fields answer, and `bench status` (ROADMAP benchmark 3) is where surfacing it belongs.

## Declared lossiness / deferrals

- **Nothing here has faced a live model.** The whole round is a bet about how mimo reads a brief,
  and no baseline is banked to score prose against (B3, parked). What can be checked cheaply — that
  the list is written at all, that loads and reads recur — is now in the archive, and it needs one
  run. `design/runner-authority.md` § Delivery says so where the next author will read it.
- **The brief got longer, not shorter.** The plan of record predicts a *shorter* reminder once
  loading is reliable and rules move back into skills. That payoff belongs to rows 2–5; this round
  paid ~35% more words for the scaffold and the split-out loading step, and trimmed only the
  duplication it could (the list is built from the step headings rather than restating them).
- **Rows 2–5 must still assume the reminder and the checker are the only per-turn text.** The third
  home does not open until a run says loading recurs.
- **`combat-reminder` was left alone.** Combat is tracker-driven and its brief is emitted per step;
  the measured failure is in the play loop.
- **The `submit_turn` question is now half-armed.** `open-questions.md` carries it: the runner has a
  todo list, so the condition is a rise in meta-breaks, which the next run answers.
- **A stale ROADMAP row was retired in passing.** B4 (the golden prompt-stream test) has been built
  and in the gate since before this loop existed; the benchmark track still listed it as remaining
  work. The code wins and the doc gets fixed in the round that notices it.

## Green bar

`python -m compileall gm_llm` clean; all fourteen `dev/test_*.py` scripts pass (the new one is
`dev/test_runner_turn.py`); `tools/status.py --check` and `tools/lint_docs.py` both clean. The
golden stream was re-recorded — its diff is exactly the four `dm-runner` messages this round
rewrote, and nothing else.

# Part 10 — Direction: freezing MiMo and starting Luna clean (2026-08-14)

## The gap

The roadmap still treated MiMo as the product target even after its pilot made the practical limit
clear. It scheduled more prompt recalibration, then a MiMo baseline, then extraction of MiMo's
hard-coded orchestration into a generic playbook, and only after all of that allowed a stronger
model's tier to exist. The sequence made the weakest model's failure modes the architecture every
later model had to inherit.

That was already visible in the supposed Tier-1 design: disable selected runtime flags, assemble
new prose from shared fragments, but preserve roughly Tier 0's stage structure. It was subtraction
from MiMo, not a design for another model.

## What the round does

MiMo freezes as the playable Tier-0 profile. Its shipped assets, the partially landed per-turn
todo/staleness experiment, and its orchestration stay available for the game and for comparison,
but the remaining recalibration rows and the prerequisite MiMo baseline are retired. Tier-0 work is
now preservation work: supported-path regressions, provider drift, and golden-stream protection
when shared substrate changes.

Tier 1 targets `opencode/gpt-5.6-luna` at `xhigh` reasoning. The model catalog and OpenAI model
documentation both expose `xhigh` between `high` and `max`; Karl's observed quality gain at higher
reasoning is the product reason to start there. Model and reasoning level are one profile condition,
not two casual knobs. A later effort comparison is an ablation with its own archive identity.

The new plan draws the start-over boundary by ownership:

- **Keep model-independent substrate:** human-readable campaign files and knowledge separation,
  deterministic dice/combat tools, transcript and completion facts, checkpoints and git ownership,
  backend/lifecycle/frontends, raw archives, grading, and the fixture.
- **Re-author model-facing behavior:** roles, agent topology, prompts, skills, context delivery,
  checker feedback, and setup/play/reconcile decomposition.
- **Do not decide the second category in advance.** Luna first gets a minimal Hollowfell live-play
  probe with no MiMo control layer. Its trace defines the contract for the first production slice.

### Why the Luna probe precedes tier plumbing

The old B5/B6 sequence would first make Tier 0 data — namespace, playbook, flags, skill set — and
then express Luna using that schema. That is speculative abstraction with an unusually strong bias:
every field is a concept MiMo already needed. A concrete Luna path provides the missing second
sample. Only then can a shared seam be named without guessing.

This does not mean duplicating the whole application. The first slice reuses proven substrate and
adds only enough selection to bypass Tier-0 behavior. If both paths later need the same configurable
mechanic, it can be extracted with two real callers and a clear contract.

### Why the checker begins observe-only

The archive and grader are useful precisely because they can observe a subject without becoming the
subject. Feeding MiMo checker verdicts into Luna would let a weaker, known-incomplete instrument
shape a stronger model's play, confounding the comparison and potentially degrading the product.
Tier 1 therefore archives the same checks but withholds correction by default. Correction delivery
can return only as a focused experiment that demonstrates a gain.

## Declared lossiness / deferrals

- No Tier-1 production code or prompt prose lands here. The next task is the diagnostic live-play
  probe; writing a reusable profile framework before that run would contradict the decision.
- The exact OpenCode configuration syntax for pinning `xhigh` is left to the probe, where it can be
  verified against the installed OpenCode version. The product condition itself is settled.
- The MiMo plan-coverage, `submit_turn`, DC-authoring, and remaining runner-authority questions are
  no longer live backlog. Parts 7–9 preserve their evidence; reopen one only if Luna reproduces it.
- The old archive label `low` remains historical data. Benchmark B5 owns a forward profile-identity
  migration rather than rewriting past runs.

## Green bar

`python -m compileall gm_llm` clean; every `dev/test_*.py` script passes; `tools/status.py --check`
and `tools/lint_docs.py` both clean. The sandbox hangs while closing even a minimal
`asyncio.to_thread()` program, so the Python 3.11 gate used a disposable `/tmp` shim that performs
the same default-executor shutdown synchronously; no repository code or test was changed for it.
This round changes planning and stable orientation only, not runtime code or model-facing assets.
