---
name: feedback-curation
description: Curate the player's session feedback into the campaign/feedback/* standing-guidance files — distilled, campaign-agnostic, routed to the right file, deduped against what's already there. Loaded by the analyst after the assessment, once the digest exists.
---

# feedback-curation — turn session feedback into standing guidance

The player's session feedback is how the system learns their preferences over time. Each piece gets
**distilled into durable, campaign-agnostic guidance** in the file that governs the behavior it's
about, so the relevant skill or agent reads it next time and adjusts. This is curation, not
transcription: the files stay a tight list of *current* standing guidance, not a pile of quotes.

## Input
- The player's feedback this session: the **Player feedback** section of the digest
  `campaign/sessions/session-{N}.md` (their words, verbatim), and `campaign/sessions/session-{N}-notes.md`
  if present.
- The routing guide and entry format: `campaign/feedback/README.md`.
- The existing `campaign/feedback/*` files you're integrating into.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Pull context
2. Distill each feedback item
3. Route and integrate
4. Self-check
5. Report

### 1. Pull context
Read the player's feedback (digest *Player feedback*, plus the session notes if present). Read
`campaign/feedback/README.md` for the routing table and entry format. Skim the feedback files you're
likely to touch.

### 2. Distill each feedback item
For each distinct point the player made, restate it as a **general standing-guidance instruction**:
the behavior they want, plus a brief *why*. Two rules:
- **Campaign-agnostic.** Name no instance content — no specific NPC, place, item, or plotline. The
  guidance shapes *how the system behaves* in general; a campaign specific belongs in canon, not
  here. ("Make information hard-won — ask for rolls on uncertainty," not "the player wanted a roll to
  read the Cartographer.")
- **Distilled, not quoted.** Capture the durable preference, not the conversational wording.

A purely non-actionable remark ("that was fun") needs no entry.

### 3. Route and integrate
For each distilled item, write it into the matching `campaign/feedback/{target}.md` per the README's
routing table (prefer the skill-level file the behavior lives in). Integrate, don't append blindly:
refine or merge with existing guidance, drop what this supersedes, and keep each file a tight list of
current standing guidance. Note the session each item came from (e.g. "(from S{N})").

### 4. Self-check
- Every actionable item of the player's feedback landed in some file.
- Each entry is distilled, campaign-agnostic, in the right file, and session-noted.
- No file has become a transcript — each is still a tight list of current guidance.

### 5. Report
Brief: **Result** (which files you wrote, and the guidance added/refined/dropped in each),
**Caveats** (any feedback you couldn't confidently route or interpret).

## Boundaries
- Your scope is **the `campaign/feedback/*` files**. Nothing else — leave canon, state, and the
  assessment alone.
