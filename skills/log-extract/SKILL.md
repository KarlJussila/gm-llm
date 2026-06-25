---
name: log-extract
description: Turn an auto-captured play transcript into the structured session digest (session-N.md). Reads the raw transcript in chunks and extracts every notable change losslessly, guided by a fixed taxonomy — it does not summarize away specifics. Used by the dm/log-extractor after a session.
---

# log-extract

## Purpose

The session runner no longer writes notes by hand — the play transcript is captured automatically
to `campaign/sessions/session-{N}-transcript.md`. This skill reads that raw transcript and produces
the **structured digest** `campaign/sessions/session-{N}.md`: the canonical session log the rest of
the system reads. The job is **lossless extraction, not summarization** — preserve every specific
(names, numbers, exact learned facts, verbatim document text). When in doubt, keep it.

## Read in chunks — never load the whole transcript at once

Transcripts can be long. Process the transcript in order, in segments (e.g. read ~150–200 lines at
a time with the Read tool's offset/limit), and append what you find to the working digest after
each segment. Track your position and continue to the end of the file. Then do one consistency
pass over the digest to merge duplicates and order events. This keeps each step bounded so nothing
is dropped for lack of context.

Also read, for grounding (so you record what's *new* and flag what changed): the session plan,
the current world files, and the PC knowledge ledger.

## What counts as a notable change — the extraction taxonomy

Extract everything in these categories. This is the definition of "notable"; if the transcript
contains it, it goes in the digest:

1. **Narrative** — a concise beat-by-beat of what actually happened, in order.
2. **Knowledge gained** — every fact the PC learned, deduced, or was told; new beliefs the PC now
   holds (mark ones that are *false*); open questions the PC became aware of. (Feeds the ledger.)
3. **Secrets & awareness** — which `[hidden]` facts were revealed to the PC (→ `[revealed: S{N}]`),
   and any change to who-knows-what (e.g. the PC told an NPC something, or an NPC learned a fact).
4. **World canon** — new or changed NPCs, locations, factions, and events, including anything the
   DM improvised: capture names and the salient details so they stay consistent.
5. **Items** — significant objects gained, lost, consumed, given, left behind, or altered (owner /
   location / state); notable gear changes.
6. **Documents** — the **verbatim** text of any written material shown to the player (letter,
   journal, inscription, sign, contract, book passage). Copy it exactly; this can't be reconstructed.
7. **Character state** — level, conditions, resources, relationships/dispositions, and any
   consequential decisions the PC made.
8. **Threads** — threads opened, advanced, or resolved; cliffhangers; what's left unresolved.
9. **Engagement** — what the player leaned into, skipped, or was excited by (for the assessment).
10. **Plan vs. actual** — where the session diverged from the plan.
11. **Player feedback** — if the session ended with player feedback, copy it **verbatim**.

## Principles

- **Extract, don't compress away specifics.** A summary that loses a name, a number, an exact
  learned fact, or a document's wording has destroyed useful data. Keep the specifics; trim only
  the conversational back-and-forth.
- **Record what's new or changed**, cross-referenced to current state — not a restatement of
  things already established and unchanged.
- **Don't apply changes to other files.** You produce the digest only; the `dm` applies it to the
  ledger, world files, items, and documents during post-session review.

## File output

Write `campaign/sessions/session-{N}.md` (the digest), organized by the taxonomy above. Leave the
raw `session-{N}-transcript.md` in place. End with a Result / Evidence / Changes / Caveats report.
