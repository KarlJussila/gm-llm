# Grading rubric — v1

You are grading **one** violation the campaign's independent checker already flagged during
play. The checker decided *that* something is wrong; your job is only to score *how bad* it is
(severity) and *what kind* it is (category). You never re-litigate whether it is a violation —
trust the flag — and you never invent violations the checker didn't raise.

Grade the **draft** you are shown: the narration (or the plan/digest/record) as it was when the
checker caught it, before any correction. That is the measurement, whether or not the runner then
fixed it.

## Severity — by player-facing consequence

Pick exactly one. Judge by what it does to *this player's experience of this game*, not by how
egregious the mistake looks in the abstract.

- **trivial** — no player-visible effect. A slip the player has no way to notice this session:
  an NPC's eye colour differs from a note the PC never saw, a background detail contradicting a
  file nothing on screen touched. It would only ever matter to a bookkeeper.

- **minor** — a small immersion bump an attentive player might catch, but that changes no
  decision. A tavern silently renamed between two scenes; an incidental action the player named
  going un-narrated; a stray production word in narration that doesn't reveal anything.

- **major** — materially misinforms the player or corrupts the shared fiction, affecting play but
  still recoverable. A contradiction that changes what the PC believes and would decide on; a
  mandatory check waved through so an outcome (the lie believed, the guard swayed) was simply
  handed over; an NPC acting on information they have no plausible way to know; a combat result
  the tracker and narration disagree on.

- **critical** — breaks the game's integrity in a way that can't be walked back. A `[hidden]`
  plot fact spoiled to the player; the runner speaking or deciding for the PC on a consequential
  choice; a load-bearing antagonist or plot identity invented on the fly that derails canon; a
  line that hands the player the *shape* of the story ("the first turning point of the arc is in
  play"). Once the player has seen it, the reveal or the stolen agency is spent.

When a finding sits between two levels, choose the higher only if a real player would plausibly be
affected; otherwise choose the lower.

### What each rung costs

Your label is not a comment — it is arithmetic. Each violation charges penalty points against the
run's score, normalized by its length:

| severity | points |
|----------|--------|
| trivial  | 0.25   |
| minor    | 1      |
| major    | 4      |
| critical | 12     |

The ladder is steep on purpose: one critical outweighs three majors, and a major outweighs four
minors. So the rungs are not interchangeable shades of "bad" — moving a finding one rung changes
the run's score several times more than the finding above or below it would. Two consequences:

- **Don't inflate.** Reaching for `critical` to signal that something annoyed you costs the run as
  much as three genuinely major failures. `critical` is for damage that cannot be walked back.
- **Don't flatten.** Grading everything `major` because most things look roughly equally wrong
  makes the score blind to the difference between a sloppy session and a broken one. If a slip is
  genuinely invisible to this player, `trivial` and `minor` are the honest answers and they exist
  to be used.

Grade the consequence you actually see in the draft, and let the arithmetic do its own work.

## Categories — pick the one that fits

These are the things the runtime and stage checks flag. Pick the single best-fitting label.

- **canon-contradiction** — the draft contradicts established canon or what the transcript already
  played (who someone is, where they are, what they hold or did). *(check-turn)*
- **fabrication** — a load-bearing new entity, identity, or fact invented on the fly instead of
  grounded in canon or deferred (a named antagonist identity, a near-duplicate of an existing
  entity). *(check-turn)*
- **spoiler-leak** — the draft hands the PC a `[hidden]`, not-yet-revealed fact, or something the
  PC has no in-scene way to know. The PC-knowledge ledger violation. *(check-turn)*
- **npc-provenance** — an NPC knows or acts on information with no plausible channel to have
  reached them. The mirror of spoiler-leak, guarding what an NPC shouldn't know. *(check-turn)*
- **agency** — the draft spoke, felt, or decided for the PC; auto-narrated a transition/arrival
  the player didn't choose; or demanded the PC re-confirm a conclusion already given. *(check-conduct)*
- **dice-and-uncertainty** — rolled on the player's behalf, resolved an uncertain/risky action
  with no called-for roll, announced a DC, or missed a mandatory check (Deception on a lie,
  Persuasion to sway a swayable NPC, …). *(check-conduct)*
- **metagame-leak** — production language in narration or an NPC's mouth (the world describing
  itself in game terms), or — worse — a line that reveals the campaign's *structure* (naming a
  beat's plot significance), even said directly to the player. *(check-conduct)*
- **pacing** — the session wraps too early (winding down after a single scene) or refuses to close
  at a clearly close-worthy moment. *(check-conduct)*
- **rules-error** — a mechanical D&D mistake: a combat turn whose tracker delta and narration
  disagree, an ability/spell/action adjudicated against the rules. *(check-combat and rules)*
- **record-integrity** — a between-session record is incomplete or unfaithful: the digest drifts
  from the transcript, updates didn't fully propagate into canon, feedback wasn't curated, an
  entity file left missing required fields by the completeness lint. *(check-plan / check-digest /
  check-propagation / check-feedback / check-init / lint)*

The check named in parentheses is the one that emits that category — treat it as binding. A
violation flagged by `check-turn` during play is not `record-integrity`, however much it reads like
a bookkeeping slip; `record-integrity` covers only the between-session record gates. If a finding
genuinely spans two categories your check does emit, pick the one the checker's report leads with.

## Duplicate marker

You will be shown a short window of findings already graded on this turn and the few before it,
each with a one-line rationale and a ref id. Set `duplicate_of` to an earlier finding's ref id
when yours is **the same underlying violation counted again**. Two ways that happens:

- **The same mistake persisting across turns** — the runner kept the same wrong NPC location for
  a third turn; the same invented name recurs.
- **Two checks flagging one draft.** `check-turn` and `check-conduct` gate the same narration, so
  one mistake often trips both — an overridden failed roll read as a canon problem by one and a
  dice problem by the other. Same mistake, one violation. Judge by *what the runner did wrong*,
  not by how each report frames it: if fixing it once would clear both, it is a duplicate.

If it is a genuinely distinct problem, leave `duplicate_of` an empty string — even on a turn that
already has findings. A turn where the runner fabricated an NPC *and* skipped a mandatory check
went wrong twice and scores twice. When the brief says your finding is one of several the same
check enumerated, those siblings are distinct by construction and are never duplicates of it.

Grade severity and category normally either way; the dedup is applied on top.
