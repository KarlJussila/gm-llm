---
name: check-digest
description: The narrative-checker's POST role, first gate — verify the session digest (session-N.md) faithfully captures the play transcript: nothing load-bearing dropped, nothing invented or distorted. Source-fidelity only (transcript vs. digest, not canon).
---

# check-digest — verify the digest faithfully captures the transcript

Digest-fidelity role. The digest is a structured extraction of the play transcript, and it's the
record the rest of the post-session work builds on — so it must faithfully reflect what was played.
Confirm the digest is a faithful, complete extraction of the transcript.

This is **source-fidelity**: compare the digest against the **transcript** only — not canon, and
not authoring quality.

## The checks

### 1. Pull both files
- Read `campaign/sessions/session-{N}-transcript.md` — the raw play record, your **source of
  truth**. Read it in chunks if long; do not skim.
- Read `campaign/sessions/session-{N}.md` — the digest under review.
- The digest is organized into standard sections — Narrative, Knowledge gained, Secrets & awareness,
  World canon, Items, Documents, Character state, Threads, Engagement, Plan vs. actual, Player
  feedback. You're checking those against what the transcript actually shows.

### 2. Check coverage — transcript → digest
Walk the transcript and confirm every **load-bearing** thing it contains made it into the digest:
- Every **named entity** introduced in play (NPC, location, faction, item) — captured under World
  canon / Items.
- Every **fact the PC learned** and every **secret revealed** — captured under Knowledge gained /
  Secrets & awareness.
- Every **consequential decision**, **thread** opened/advanced/resolved, and **plan divergence**.
- Any **verbatim document** read aloud — copied into Documents (exact text, not paraphrased).
- The **player feedback** exchange, if the session ended with one — copied verbatim.
Flag anything the transcript establishes that the digest dropped. Trivial conversational back-and-
forth that establishes nothing is *correctly* omitted — don't flag it.

### 3. Check fidelity — digest → transcript
Walk the digest and confirm every claim traces back to the transcript:
- No **invented** beat, fact, name, number, or reveal that the transcript doesn't support.
- No **distortion** — a name, a quantity, a quoted document, or who-learned-what changed from what
  the transcript actually shows.
- Flag each unsupported or altered claim, with the digest line and what the transcript actually says.

## Report
Per finding: whether it's a **drop** (in transcript, missing from digest) or an
**invention/distortion** (in digest, unsupported by transcript), the **transcript evidence** (a
quote or beat), and the **digest location** it should be fixed at.
