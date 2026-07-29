# Runner authority — what `dm-runner` may and may not author

Plan of record for the prompt recalibration workstream. What the system is →
[README.md](README.md); the benchmark that surfaced the gaps → [benchmark.md](benchmark.md).

**Sequencing lives in `ROADMAP.md` track recalibration.** This doc says what the rule *is* and
where the current prompts disagree with it; it does not say how far the work has got.

## The model

The runner is an **executor of a plan**, not a co-author of the campaign. Its licence to invent
is narrow, and it is narrower than the current prompts allow.

1. **Planned content is binding.** Where documentation exists, it is adhered to — most of all the
   *what it means* portion. Planned content should not diverge. The plan is not a suggestion the
   runner weighs against its own instincts mid-scene.
2. **Improvisation is licensed by the player, not by the runner.** The runner may improvise when
   the *player* goes off the track. It may not decide on its own to go somewhere the plan did not
   put it.
3. **Improv still respects canon, and treads lightly on new canon.** Going off-plan is not
   permission to contradict established facts, and it is barely permission to establish new ones.
4. **No new entities of substantial consequence.** The runner does not author identities,
   factions, places, or items that carry weight.
5. **Nothing that outlives the session.** Ideally the runner authors no new detail or entity
   likely to matter beyond the current session.
6. **Never arc-impacting lore.** An absolute. Lore that touches an arc is authored between
   sessions, by `dm`, through the gated pipeline — never improvised at the table.
7. **Never unauthorized revelation.** The runner never hands the player hidden information that
   the session plan did not list as revealable this session (or place with an NPC the plan
   staged). Also absolute.
8. **Prefer an abrupt end to heavy improvisation.** Running out of planned material is a better
   outcome than inventing to fill the time. Stopping early is a legitimate move; improvising a
   session's worth of new world is not.

**DCs are the soft part.** Difficulty numbers in a session plan are low-importance and arguably do
not belong there at all — they are the one thing in a plan the runner may treat as advisory. This
is the inverse of the intuition that the mechanical bits are binding and the story bits are
flexible; the reverse is closer to true here, though neither is exactly right.

## Where the prompts currently disagree

Found by reading the runtime gate against the model above, during the benchmark pilot
([`dev/fixtures/hollowfell/pilot-2026-07-29.md`](../dev/fixtures/hollowfell/pilot-2026-07-29.md)).
Each is a gap between what the model requires and what a prompt actually says.

| # | Where | The disagreement |
|---|---|---|
| 1 | `check-turn` § preamble | *"Consistency, not obedience… diverging from the arc is allowed and only recorded."* Licenses divergence **generally**; the model licenses it only when the *player* initiated it. The line's intent — don't flag the runner for following a player off-track — is right; its scope is too wide. |
| 2 | `check-turn` § preamble | *"A draft that adds new detail consistent with the transcript is ordinary play — flag a conflict…, never mere addition."* Check 4 triages **newly-named things** only, so arc-touching lore that names no entity is "mere addition" and passes both. That is rule 6, the absolute one. See the worked case below. |
| 3 | `check-turn` § 5 | Spoiler discipline is judged against `[hidden]` flags **in canon**. Information the runner *invented* has no flag to trip, and the plan's list of what is revealable this session is never consulted. Rule 7 is therefore unenforced in its stated form; what is enforced is the weaker "don't reveal canon marked hidden." |
| 4 | orchestrator | The session plan is **not** preloaded to the runtime checker. `Canon.build()` assembles baseline canon + draft-named entities + transcript tail; the plan goes to `Canon.runner_preload()` only. Adjudicating rule 7 needs the plan's revealable list on the checker's side. |

Gaps 1–3 are prose. Gap 4 is a small orchestrator change (or on-demand reading — the checker holds
`read`/`glob`/`grep`, and `check-feedback`/`check-init` already read `campaign/` on demand — but the
runtime gate opens a fresh session per turn, so re-reading a whole plan every turn is the expensive
option).

### The worked case for gap 2 — the geologist

From the pilot's `5c16`, and the reason gap 2 is not hypothetical. Two inventions in one session,
one caught and one not:

- **"Aldric Voss"** — a named antagonist identity with backstory. Check 4 fired, blocked it, and
  the grader scored it the batch's most severe finding. The system worked.
- **"A geologist, sent by the consortium, three months ago"** — spoken by Brennan, an existing
  canon NPC. The word *geologist* appears **nowhere** in the fixture: not in canon, not in the
  session plan. The runner authored the antagonist's cover identity and a three-month timeline,
  and attached it to the **consortium**, which *is* canon. Nothing flagged it.

The difference is not consequence — the geologist is arguably the more load-bearing of the two —
it is that Voss had a proper name and the geologist had a role. Check 4 triages "the draft's
newly-named things"; an unnamed actor never enters the triage, and the preamble's "never flag mere
addition" then covers it. A recalibrated check has to catch **new plot-load-bearing actors and
lore regardless of whether they were given a name.**

It also raises a question rule 7's wording does not settle: the geologist was delivered *through
an NPC the plan stages*. Rule 7 permits revelation "by an NPC the plan staged", which can be read
as licensing whatever a staged NPC says. It should not — staging an NPC authorizes the NPC, not
arbitrary content in their mouth. Wording to settle in the ruleset review.

**Rule 8 is already well covered** and needs no work: `session-flow` § Pacing states it
("Heavily improvised territory is itself a reason to close"), `session-run` marks that skill
always-loaded, and `turn-reminder` step 5 carries a compressed form into *every* turn. It is listed
here only so a later reading doesn't mistake its absence from the gap table for an oversight.

## Delivery: stating a rule is not the same as landing it

A constraint that shapes every row above. **The runner will not read a file or load a skill unless
it is told to on that turn** — mid-narration it stays in flow and stops checking things. That is
what `turn-reminder` exists for, and it is why rule 8 is in the reminder rather than left to the
skill that owns it.

`CLAUDE.md` § Writing prompts already says a universal rule parked in an unloaded skill is silently
absent. This is the stronger form: *loading is not salience.* Even an always-loaded skill is applied
weakly once narration is underway, so a rule the runner must apply **mid-flow** has to be either in
`turn-reminder` or enforced by the checker — not merely stated somewhere correct.

Consequences for this workstream:

- Rules 6 and 7 are absolutes the runner must honor on every turn, so they cannot be addressed by
  prose in a skill alone. Gaps 2 and 3 are written against the **checker** for that reason: the
  gate catches what the reminder cannot carry.
- `turn-reminder` is the scarcest real estate in the system and is already dense (five numbered
  steps, each long). Anything added there displaces attention from what is already there.

**But detection is the floor, not the goal.** A violation the checker catches is still a violation
the runner committed, and gm-llm is a game as well as a benchmark — a corrected draft costs a turn
and a correction budget every time. So each gap has two halves:

1. **Flag it** — the checker must be able to see the violation at all. This is what gaps 1–4 are
   about, and it is the prerequisite for measuring anything.
2. **Stop needing to** — the runner must carry the rule without being caught. That is the harder
   half and the one that decides whether the product is good, not merely measurable.

Getting a light model to hold a rule mid-narration is the actual craft problem. The tier ladder is
how it gets measured: at the bottom, *how small a model can we make run a clean game?* — above it,
*how much framework does a stronger model need to run one?* (`benchmark.md` § Goal). A
recalibration that only teaches the checker to complain would raise the violation count and improve
nothing.

## The model is provisional — it needs a proper review

§ The model above was transcribed from one conversation and has **not** been worked through with
Karl section by section. It is good enough to sequence work against and not good enough to author
prompt prose from. Before track **recalibration** row 1 starts, two passes are owed:

1. **The ruleset itself** — an extended back-and-forth to settle the rules' scope and wording.
   Known-open from the transcription: whether rules 4 and 5 are one rule or two (they were said as
   one thought); whether rule 8 is a rule or a corollary of rule 3; how hard "DCs are advisory"
   actually is; and rule 7's "or an NPC the plan staged", which as written can be read as licensing
   whatever a staged NPC says (see the geologist case).
2. **The prompts, section by section** — read the existing agents, skills and briefs against the
   settled ruleset and record every divergence, rather than only the ones a benchmark run happened
   to surface. The gap table above is what one pilot exposed; it is not an audit.

## Deliberately out of scope here

Two things this doc is *not* the home for, so a reader does not go looking:

- **Plan coverage** — a session can honor every rule above and still under-deliver its plan, which
  the pilot caught and nothing measures. That is a question about the *instrument*, not about the
  runner's authority: it lives in `open-questions.md` § Benchmark, on track **recalibration**.
- **Whether `dm` keeps authoring DCs** — the rule above settles their *weight* (advisory); whether
  they belong in a plan at all is a planner question, and it is ROADMAP **recalibration** row 4.

## Consequences for the benchmark

Recalibrating these prompts changes the subject under test, so **every archive taken before it is
superseded** — the prompt fingerprint is part of the condition precisely so this is visible rather
than silent. The pilot's *methodology* findings survive (they are properties of the measurement
design); its *scores* do not describe the recalibrated system. `ROADMAP.md` sequences the two
tracks against each other.
