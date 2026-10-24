# Grading rubric — v3

Each finding is a claim that the DM, or a between-session record, got something wrong. First decide
whether it holds; then, if it does, how bad it is and what kind it is.

## Confirm or reject

Confirm a finding when the files and the transcript bear it out and it is a violation by the
categories below. Reject it when the evidence doesn't hold, canon or earlier play supports what the
DM did, or it is ordinary play the categories don't cover. A rejection costs the run nothing and
counts against the checker's precision, so reject freely when the claim is wrong — and never
reject a real mistake because the checker described it badly.

Grade the turn as it was played: the narration the player saw, not anything fixed later.

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
  check waved through so an outcome (the lie believed, the guard swayed) was simply handed over;
  an NPC acting on information they have no plausible way to know; a combat result the tracker and
  narration disagree on.

- **critical** — breaks the game's integrity in a way that can't be walked back. A `[hidden]`
  plot fact spoiled to the player; the DM speaking or deciding for the PC on a consequential
  choice; an improvised antagonist or plot identity that contradicts canon and derails it; a
  line that hands the player the *shape* of the story ("the first turning point of the arc is in
  play"). Once the player has seen it, the reveal or the stolen agency is spent.

When a finding sits between two levels, choose the higher only if a real player would plausibly be
affected; otherwise choose the lower.

### What each rung costs

Your label is arithmetic. Each confirmed violation charges penalty points against the run's score,
normalized by its length:

| severity | points |
|----------|--------|
| trivial  | 0.25   |
| minor    | 1      |
| major    | 4      |
| critical | 12     |

One critical outweighs three majors, and a major outweighs four minors, so moving a finding one
rung changes the score several times more than the rung below it would. Don't reach for `critical`
to signal annoyance, and don't flatten everything to `major`: `trivial` and `minor` exist to be
used when a slip is genuinely small.

## Categories — pick the one that fits

- **canon-contradiction** — contradicts established canon or what play already established (who
  someone is, where they are, what they hold or did).
- **fabrication** — an improvised entity, identity or fact that conflicts with canon, quietly rules
  out something the plan has waiting, or near-duplicates an existing entity.
- **spoiler-leak** — hands the PC a `[hidden]` fact it hasn't learned, something it has no in-scene
  way to know, or a coming beat.
- **npc-provenance** — an NPC knows or acts on information with no plausible route to them.
- **agency** — spoke, felt or decided for the PC; narrated a transition the player didn't choose;
  made the player restate a conclusion already given.
- **herding** — pushed the player toward the plan: pressed a hook again and again, inflated it, left
  the alternatives thin, or pressed a choice the player had already made or not taken up.
- **dice-and-uncertainty** — rolled for the PC, resolved an uncertain action with no roll,
  announced a DC, or let a social move land with no check (a lie always takes Deception).
- **metagame-leak** — production language in the fiction, or a line that reveals the campaign's
  structure (naming a beat's plot significance), even said to the player directly.
- **clarity** — narration whose meaning was lost in flavour or unexplained terms, or that
  over-explained what the scene already made clear.
- **pacing** — wound down after a single scene, or refused a clearly close-worthy landing.
- **rules-error** — a mechanical D&D mistake: tracker and narration disagree, a reaction or
  ability used against the rules.
- **record-integrity** — a between-session record is incomplete or unfaithful: a plan, digest or
  propagation the gate flagged, feedback not curated, an entity file the lint found incomplete.

Turn findings take one of the first nine; `record-integrity` is for stage findings only.

## Duplicates

Set `duplicate_of` to the ref of an earlier confirmed finding when this one is **the same
violation counted again**: the same wrong fact carried into a later turn, or one mistake the
checker described twice. The checker marks the first kind with `continues`; check it rather than
trusting it. Judge by what the DM did wrong: if fixing it once would clear both, it is a duplicate.
A turn that went wrong in two unrelated ways scores twice. Grade severity and category normally
either way; duplicates are dropped from the score afterwards.
