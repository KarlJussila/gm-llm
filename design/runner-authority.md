# Runner authority — what `dm-runner` may and may not author

Plan of record for the prompt recalibration workstream. What the system is →
[README.md](README.md); the benchmark that surfaced the gaps → [benchmark.md](benchmark.md).

**Sequencing lives in `ROADMAP.md` track recalibration.** This doc says what the rule *is*, where
the current prompts disagree with it, and what stops a rule from landing; it does not say how far
the work has got.

## The model

The runner is an **executor of a plan**, not a co-author of the campaign. Its licence to invent is
narrow, and it is narrower than the current prompts allow. Six rules, settled section by section:

1. **Planned content binds; planned mechanics advise.** Identities, answers, what an NPC knows,
   what's revealable — fixed, and most of all the *what it means* portion. DCs, which skill,
   check-gated vs. player-assembled — the runner's call, so long as it follows the mechanics craft
   it already has.
2. **Improvisation is licensed by the player, never by the runner.** The runner may improvise when
   the *player* goes off the track. It does not decide on its own to leave the plan.
3. **The plan fixes what can be learned, not the only route to it.** If the player bypasses the
   intended source, a *plausible* alternative route to the same fact may work — behind a fitting
   check. Three hard limits:
   - **Plausibility.** The route has to make sense where they are. A library holds records, not a
     foreman's opinions. If there is no sensible channel where they are looking, they do not find it
     there — that is a real dead end, and dead ends are allowed.
   - **Last resort, not default.** Use it when the intended source has genuinely been passed by.
     Don't strew leads: the player tripping over the plot everywhere they go is worse than missing
     it once.
   - **Never move an NPC, a place, or an object to make it work.** The world does not rearrange
     itself around the player.
4. **What you invent may complicate the character, never the plot.** Absolute. Gold, rations, a
   wound, a favor owed, a guard who chases them off — free, and that guard may have a name and
   motives. An arc, a thread, a clock, or the answer to anything the player is investigating —
   never.
5. **Two sources, one question — where did this come from?** When the draft tells the player
   something they did not know: **from the plan or canon** → only if this session is authorized to
   reveal it; **from you** → only if it is *entailed* by what is written, or nothing hangs on it.
   Also absolute.
6. **Off the plan with no route back is a closing signal, not a mode of play.** Once you are
   improvising with no planned material in reach, land it within a beat or two. Inconsequential
   scenes are the walk to the exit — never a way to keep playing.

The compressed form, for wherever the runner must apply this mid-narration:

> **Did I make this up? Then it can complicate the character — never the plot.**

Two supporting definitions the long form needs:

- **Entailed** — what a reader of the file would already take for granted. The king has a crown, the
  tavern has a bar and a smell, the miner's hands are callused. Not authoring; *rendering* what canon
  already implies. Consequence is irrelevant here — important entities need this most, because they
  are the ones on screen.
- **Inconsequential** — true of the world, but nothing hangs on it. The foreman's lunch, the
  corner-guy's name, the weather. Test: if it is never mentioned again, nothing is lost.

### What the settling changed

Recorded because the earlier eight-rule form is quoted in Part 7 and a reader will notice:

- **"Nothing that outlives the session" was scoped wrong and is gone.** Duration is not the line —
  rations, a named guard and a nameless miner all outlive the session and are all fine. **Story
  impact is the line.** Three rules (no consequential entities / nothing that outlives the session /
  never arc-impacting lore) collapse into rule 4.
- **The staged-NPC carve-out is cut.** Staging an NPC authorizes the NPC, not arbitrary content in
  their mouth; their dialogue is governed by rule 4 like anything else. Worked set: "I don't know" —
  fine. "I don't know", lying — fine, it comes from the plan's `Known to:` / concealed tells. The
  foreman's lunch — fine. "A sketchy guy went down into the mines last week", to a player
  investigating the mines — blocked.
- **Rule 3 is new**, and it is the only rule in the set that says *yes*. It is also the runner-side
  half of the plan-coverage question in [`open-questions.md`](open-questions.md) § Benchmark.
- **Closing early was demoted from a response to divergence to a response to exhaustion.** The
  previous form let a runner spend twenty turns on individually-harmless scenes and stay compliant.

## Delivery: the runner reads the campaign once and then narrates from memory

This section outranks the audit below. A rule that cannot reach the runner mid-scene is not a rule,
and the measurements say almost nothing currently does.

Counted from the five pilot runs' opencode session records (`~/.local/share/opencode/opencode.db`,
`part` rows of type `tool`), across roughly 125 runner turns:

| | |
|---|---|
| Skills loaded | `session-run`, `session-flow`, `discoveries` at **turn 1** in every run; `social-play` at turn 1 twice, mid-session twice, never once; `session-close` near the end in every run |
| Skills **re**-loaded | none, in any run |
| Canon `read`/`glob` | all at turn 1, plus one `glob` near the close (hunting the plan's advancement line). **One** mid-session lookup across all five runs |
| The runner's own `dice` | six calls, total |

Three things follow, and they are the constraints every recalibration row has to design against.

**Loading is not the problem; re-loading is.** The runner does load `discoveries` — always, every
run. It reads it on turn 1 of a session that runs to turn 41 and never opens it again. `turn-reminder`
step 4 names `social-play` and `discoveries` on *every* turn, and after turn 1 the runner treats the
instruction as already satisfied. `session-close` is the apparent exception only because it is gated
on a condition that is not true until late — not because it is named more often.

**"Always loaded" means "loaded once."** `session-run` sits on exactly the same footing as the
companion skills the corpus treats as optional. The only text with genuine per-turn presence in the
system is `turn-reminder`.

**Invention is substantially a staleness problem.** By turn 24 the runner is narrating a campaign it
last looked at twenty-three turns ago, from memory, with the canon far behind it in context. No
prompt rule fixes staleness. This is why rule 4 cannot be addressed by prose alone.

### The consequence for where rules live

While loading is unreliable there are two homes for a mid-flow rule — `turn-reminder`, or the
checker — and `turn-reminder` is the scarcest real estate in the system. **Make loading reliable and
a third home opens**, and the reminder gets *shorter* rather than longer: a dispatch list instead of
a rulebook, with the rules back in skills that are actually read at the moment they apply. That is
the bet behind the reminder-as-algorithm row on the track, and it is why that row runs before the
rows that author rule prose.

**What the reminder now does about it.** The brief opens every turn with a `todowrite` list whose
second step is loading for *this* beat and re-opening what the scene turns on (`dm-runner` holds the
tool it was the only agent to lack), and the orchestrator — not the prose — counts the turns since
the runner last called `skill`/`read`/`grep`/`glob`, saying so with the count once it passes five.
That count is orchestrator-side for the same reason the wrap countdown is: a line that never changes
stops being acted on, which is exactly what this section measures. **Built, not yet observed against
a live model.** Whether it took is read off each turn's `tools`/`stale` fields in the run archive;
until a run says so the third home is not open, and the rows that author rule prose should still
assume the reminder and the checker are the only text that reaches a turn.

### Detection is the floor, not the goal

A violation the checker catches is still a violation the runner committed, and gm-llm is a game as
well as a benchmark — a corrected draft costs a turn and a correction budget every time. In the pilot
runs roughly a third of drafted turns were corrected. So each gap has two halves: **flag it** (the
checker must be able to see the violation at all — the prerequisite for measuring anything) and
**stop needing to** (the runner carries the rule without being caught). The second is the harder half
and the one that decides whether the product is good rather than merely measurable. The tier ladder
is how it gets scored: at the bottom, *how small a model can we make run a clean game?*; above it,
*how much framework does a stronger model need?* ([`benchmark.md`](benchmark.md) § Goal). A
recalibration that only teaches the checker to complain would raise the violation count and improve
nothing.

## The audit — every prompt against the six rules

Read section by section: `dm-runner`, `session-run`, `session-flow`, `social-play`, `discoveries`,
`session-close`, `turn-reminder`, `runner-header`, `check-turn`, `check-conduct`, plus the planner
rows that feed rules 1 and 5.

| Prompt | 1 content binds | 2 player-licensed | 3 routing | 4 no plot impact | 5 two sources | 6 close |
|---|---|---|---|---|---|---|
| `dm-runner` | — | — | — | — | canon branch | pointer |
| `session-run` | — | — | — | — | canon branch | — |
| `session-flow` | — | — | **absent** | — | — | partial |
| `social-play` | — | — | — | **absent** | provenance only | — |
| `discoveries` | **inverted** | — | — | — | — | — |
| `session-close` | yes (advancement) | — | — | — | yes (closing) | yes |
| `turn-reminder` | mechanics only | — | — | — | — | yes (step 5) |
| `runner-header` | — | — | — | — | canon branch | — |
| `check-turn` | — | too wide | n/a | name-gated | canon flags | n/a |
| `check-conduct` | — | — | n/a | n/a | n/a | partial |

The runner-facing path scores nothing on rules 1–4. This is not weak coverage; the rules are absent.

### The five findings

**F1 — `session-run` § "Table craft — non-negotiable" contains none of the absolutes.** Its four
bullets are the player-declares boundary, the impossible-declaration boundary, who rolls dice, and
ask-for-rolls-often. All four govern **runner vs. player**. Nothing governs **runner vs. canon**. The
always-loaded core's own non-negotiable section is missing rules 1–4. Primary hole; necessary to fix
and — per § Delivery — not sufficient.

**F2 — `turn-reminder` spends its scarcest words on the axis rule 1 calls advisory.** Step 3 (ask for
a roll) is by far the longest of the five steps and is entirely mechanics. The absolutes get none.
Its length is earned scar tissue — several early campaigns would not ask for checks at all — and rule
1 does not threaten it: step 3 governs *whether to ask*, which stays binding craft; rule 1 demotes
only the plan's specific DC, which step 3 never claims. So the absolutes need *new* space, not
reclaimed space. Step 4 is the candidate, being the one step that does nothing after turn 1.

**F3 — `discoveries` binds the plan on exactly the wrong axis.** *"Follow the plan's resolution mode.
The session plan flags each discovery as player-assembled or check-gated"* enforces the mechanical
flag, which rule 1 makes advisory. Meanwhile `session-plan` § The one rule forces the planner to fix
*"the answer behind a mystery"* and `investigation-plan` emits **the committed answer** — and no
runner-facing prose says that answer binds. The plan's mechanics are enforced and its content is not.

**F4 — `social-play` grants NPC autonomy without bounding where the NPC's material comes from.**
*"The NPC plays their own hand… aims, doubts, and limits… personal agendas: some transactional, some
two-faced."* Correct craft, and the licence the geologist rode in on — Brennan playing his own hand.
The skill has a provenance rule for what an NPC may *know* and none for what the runner may *invent*
in their mouth. Some of this is better fixed in `npc-plan`, which already commits *"disposition,
agenda, what they know, how they react, concealed tells"* per NPC: every trait the plan commits is one
the runner cannot invent. Whether that block is rich enough is a planner-side audit still owed.

**F5 — `check-turn`'s defect is its classification criterion, not its intake.** See the worked case.

### The worked case — the checker approved the geologist

From the pilot's `32e6`. The gate did not miss the invention; it examined it and passed it. Turn 24,
`check-turn`, clean pass, verbatim:

> The geologist is a **legitimate new entity introduced through NPC testimony** — a natural response
> to the player's question about unusual visitors, **consistent with the world** (consortium sends
> personnel) and the mystery. No spoilers leaked… **The geologist should be registered in the INDEX
> post-session.**

It passed on the two rules this round cut: *consistency, not obedience* (it does not conflict, so it
is "mere addition") and the staged-NPC carve-out (*introduced through NPC testimony*). In the same
breath it computed that the thing needs a canon file — the predicate that should have blocked it —
and drew the opposite conclusion.

The next turn it blocks "Aldric Voss", stating its operative distinction outright: *"The geologist was
established in the transcript (line 431) **but never named**."* Two turns later it passes a fabricated
mine sign-in roster as *"ambient world-building that doesn't conflict with existing canon."*

So the checker asks **"does this conflict?"** where rule 4 asks **"does this touch the plot?"**, and
a proper name is what escalates. Check 4's classes are nearly right already (*"ambient color… with no
plot weight"* vs *"load-bearing"*); what must change is the **test**, re-cut on arc / thread / clock /
live-investigation impact, with intake widened to anything the draft asserts that is in neither canon
nor the transcript. Widening intake alone would have changed nothing here.

It also answers an objection raised against putting "would this need a canon file?" in front of the
runner — that the runner has no reason to know the registration rules. Empirically the same model
computes that predicate unprompted. The knowledge is present; only the consequence is missing.

### Secondary divergences

- `dm-runner` frontmatter names **improvisation** as one of four pillars of the job. § Boundaries is
  the natural home for rule 4 — already the "what you may not do" section, currently holding two of
  six rules.
- `session-flow` § Pacing treats *"the player skipped the planned scenes"* purely as a **close**
  trigger. Under rule 3 the first response is routing; closing is what happens when routing fails.
- `session-run` § Spoiler discipline tests reveals against the **ledger + `[hidden]` in world/arc
  files**. The plan's per-session `(known)` / `(new reveal)` / `(stays hidden)` flags are never
  consulted, so a fact marked `(stays hidden)` this session but not `[hidden]` in canon is
  unprotected. `check-turn` check 5 has the same defect — and the plan already carries those flags,
  so rule 5 is enforceable today.
- `runner-header` frames the plan as *"your prepared script — full of spoilers that are yours to
  hold."* Spoiler-bearing, yes; **binding**, never said.
- `session-plan` *"Keep 30–40% unplanned. Leave room for improvisation"* needs reconciling with rules
  2 and 3. Its rider — *"that openness is the **path**, not the **facts**"* — is the closest thing to
  rule 4 anywhere in the corpus and should be promoted, not rewritten.
- `check-conduct` § 5's **"Wrapping too early"** bullet is dropped by decision (no teeth; never
  fired), which also dissolves its collision with rule 6. `session-close` step 1's single-scene floor
  is its runner-side twin and is softened, not cut.

### A standing criterion the audit adopted

**An agent is told about machinery only where recognizing it changes its behavior.** `dm-runner`'s
`<turn-reminder>` / `<correction>` / `<prepared-context>` tags stay — it must not echo what it does
not recognize. "The orchestrator runs you" goes. Test every reference in the corpus with *"what does
the model do differently for knowing this?"*

## Deliberately out of scope here

- **Plan coverage** — a session can honor every rule above and still under-deliver its plan, which
  the pilot caught and nothing measures. That is a question about the *instrument*:
  [`open-questions.md`](open-questions.md) § Benchmark, on track **recalibration**.
- **Whether `dm` keeps authoring DCs** — rule 1 settles their *weight* (advisory); whether they
  belong in a plan at all is a planner question, on the same track.

## Consequences for the benchmark

Recalibrating these prompts changes the subject under test, so **every archive taken before it is
superseded** — the prompt fingerprint is part of the condition precisely so this is visible rather
than silent. The pilot's *methodology* findings survive; its *scores* do not describe the
recalibrated system.

One recalibration change is measurable **without the grader**: mid-session reads, skill loads per
turn and grep counts are deterministic observations, not subject to the pilot's ±17. Whether the
reminder-as-algorithm took can be read from a single run. The run archive now carries it per turn
(`tools` — what the runner called while drafting — and `stale`, the turns it had then gone without
opening anything), so this is a read of `bench-out/`, not of opencode's session DB. Surfacing it
belongs in `bench status` (ROADMAP benchmark 3) rather than being re-derived by hand.
