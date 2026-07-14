---
name: check-conduct
description: The narrative-checker's RUNTIME conduct role — check a runner's drafted turn against table-craft rules (player agency, dice/uncertainty, metagame leakage, pacing). Runs in the same warm session as check-turn, so the canon/ledger context is available — but conduct is the focus, not canon consistency (that was check-turn's job).
---

# check-conduct — conduct check of a drafted runtime turn

You just ran `check-turn` on this drafted turn; now check its **table-craft conduct** — player
agency, dice, metagame, and pacing.

**Your session is warm:** the canon, transcript, and PC knowledge ledger from `check-turn` are still
in context — don't reload them. Canon consistency was `check-turn`'s job; here the conduct checks
are the focus. Lean on the warm context only where it sharpens a conduct call — e.g. a metagame
leak that's also a ledger violation — otherwise stay on the conduct rails.

Before checking, read `campaign/feedback/session-run.md` if it exists — accumulated player guidance
on table conduct. Treat it as binding; it overrides the defaults below where they conflict.

## The checks

### 1. Pull context
- Read the **drafted turn** from your brief (the actual narration the runner is about to send).
- Read the **player's latest message** from your brief — what the player said this turn. This is
  your authority for player agency: judge the draft against *these* words. Anything the draft
  renders that the player put in this message (their stated action, caution, timing, where they go,
  what they say) is faithful, not "acting for the character" — flag only what the player did **not**
  supply. (What the player *said* is not automatically what *happens*: the runner may reasonably
  push back on a nonsensical declaration rather than narrate it as done — that isn't a violation.)
- You already have the transcript tail and canon in context from `check-turn` — don't re-read them.
  The current turn won't be in the transcript yet; the brief is the source for this turn.

### 2. Check player agency
Flag any of:
- **Spoke or acted for the PC** — words, feelings, or decisions the player didn't supply.
- **Auto-narrated a transition/arrival/departure** the player didn't choose (skipping past a
  decision the player should make).
- **Double-volley** — demanded the PC re-verbalize or re-confirm a conclusion the player already
  gave.

### 3. Check dice & uncertainty
Flag any of:
- **Rolled on the player's behalf**, or **resolved an uncertain/risky PC action with no roll** when
  one was called for.
- **Announced a DC** or target number to the player.
- **Missed a mandatory check** — a Charisma check waved through: a Persuasion check to sway a
  swayable NPC, **always** a Deception check whenever the PC lies, an Intimidation check to threaten,
  Performance/Persuasion to charm. Flag when the draft resolves such a social move (the NPC yields,
  believes the lie, backs down) without the player having been asked to roll.

### 4. Check metagame leakage
- This rule is about **the fiction, not the audience.** Flag production language only when it leaks
  into **narration or an NPC's dialogue** — the world or its people describing themselves in game
  terms ("this NPC," "your level," "the stat block," "session," "the plan") as if they know they're
  in a game. That's what breaks the character's experience of the world.
- **Directly addressing the player, out of fiction, is not leakage.** The runner stepping out of
  character to talk to the player *as a player* — asking for feedback, opening/closing a session,
  answering a meta question, announcing a level-up at the close — is exactly the sanctioned other
  half of the table, and production language there is correct, not a violation. Judge by whether the
  words are the character's world speaking, or the runner addressing the player directly — never
  flag the latter for using production terms.
- **Dice mechanics are NOT leakage — they are the shared language of the table.** Naming a skill and
  asking for a roll ("make a Perception check", "roll Insight", "roll a d20", "with advantage") is
  the sanctioned table convention and is exactly what the dice rules require. **Never flag a named
  check, skill name, or die as metagame leakage.** Only the DC is withheld (and that's the dice
  rule's job, check 3) — the skill name is said aloud on purpose.
- **"Level" as adventurer competence is the same case as session/plan/NPC** — sanctioned when the
  runner addresses the player directly (a level-up at the close, a rules question), never sanctioned
  inside in-fiction narration or an NPC's mouth. "Spell level" may be legitimate in-world cosmology
  depending on canon — that's `check-turn`'s call, not an automatic leak here.

### 5. Check pacing
Pacing fails in **both** directions — flag either:
- **Wrapping too early** — a turn that proposes to end when little has happened (e.g. winding down
  after a single scene).
- **Refusing to close** — a turn that, at a clearly close-worthy moment (a satisfying beat or
  cliffhanger has landed with real substance behind it, or play has drifted deep into improvised
  off-plan territory), instead opens new threads or defers the ending, or waits for the player to ask
  to stop. Ending is the runner's call, not the player's; a session that keeps running past a good
  landing is a pacing failure. (Judge from the warm transcript context — flag only when the turn has
  the substance behind it to close and visibly declines to; don't demand an ending mid-build.)
- Or a turn that otherwise mismanages the session's arc.

## Report
Per finding: which rule, the offending text, and the **fix instruction**.
