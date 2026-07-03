---
name: session-review
description: Assess a played session from its digest — plan vs. actual, player engagement, per-arc impact with concrete adjustment recommendations, and notes for the next plan. Produces the assessment document the arc pass and next-session planning build on. Loaded by the analyst between sessions.
---

# session-review — assess the session for the arc pass and next plan

Between sessions, this turns the digest into strategy: what the session did to the campaign, and what
each arc and the next plan should do about it. Analytical and forward-looking — you assess and
recommend; the passes that follow act on it.

## Input
- The **digest** `campaign/sessions/session-{N}.md` — what was played (your main source; the raw
  `session-{N}-transcript.md` is there if you need to check exact wording or tone).
- The **plan** `campaign/sessions/session-{N}-plan.md` — what was intended, to compare against.
- The **active arcs** `campaign/arcs/*.md` (+ `.state.md`) and the **threads**
  `campaign/state/threads.md`.
- The **PC knowledge ledger** `campaign/characters/{pc}.knowledge.md` — what the player now knows.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Plan vs. actual & engagement
2. Per-arc impact & recommendations
3. Threads & next-session notes
4. Write the assessment

### 1. Plan vs. actual & engagement
What was planned, what actually happened, and the key deviations — which beats landed, which were
skipped, what emerged unplanned. Then the engagement read: what the player leaned into, skipped, or
lit up at; where energy dipped; what held their attention. Be honest and specific — this is what the
next plan steers by.

### 2. Per-arc impact & recommendations
For **each arc the session touched**, write a short, concrete recommendation the arc pass can act on
directly:
- **What play did to it** — turning points landed, answers engaged or contradicted, the path the
  player took, where it now sits on its tension curve.
- **What it needs** — the adjustment, named with the working vocabulary as a lens: redirect,
  accelerate / decelerate, deepen, recommit a strained answer, merge / split, or resolve. Be
  concrete — "the player sided with the antagonist; the betrayal turning point needs recommitting
  toward an uneasy alliance," not "needs work."

Also flag any **thread that has grown into a candidate minor arc** (enough committed answers +
turning points to deserve real structure), so planning can promote it.

### 3. Threads & next-session notes
What threads advanced, emerged, or resolved; what's left hanging. Then what the next session's plan
should address — threads to pick up, player interests to revisit, pressure that should pay off.

### 4. Write the assessment
Write it all to `campaign/assessment/session-{N}-assessment.md`, organized under those headings.
Keep it tight and actionable — a planning tool, forward-looking, not a recap of every beat.

## Verify against the transcript
Write from the digest — that's what it's for, and it keeps your context lean. Then spot-check the raw
transcript (`campaign/sessions/session-{N}-transcript.md`) for the moments where exact dialogue,
tone, or player intent carries nuance the digest may have flattened — an engagement read, a stated
reason, a verbatim line — and correct or add as needed. Don't reload the whole transcript up front.

## Boundaries
- Your output is **the assessment document**. You recommend changes; you don't make them — leave
  canon, state, and the arcs as they are.
