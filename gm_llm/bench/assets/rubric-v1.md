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

If a finding genuinely spans two categories, pick the one the checker's report leads with.

## Duplicate marker

You will be shown a short window of findings already graded on the previous turns, each with a
one-line rationale and a ref id. If the finding you are grading is the **same underlying
violation persisting** — the runner kept the same wrong NPC location for a third turn, the same
invented name recurs — set `duplicate_of` to that earlier finding's ref id. A persisting
violation must not multiply the score. If it is a fresh, distinct violation, leave `duplicate_of`
an empty string. Grade its severity and category normally either way; the dedup is applied on top.
