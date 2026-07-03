---
name: check-feedback
description: The narrative-checker's POST role — verify the player's session feedback was curated into campaign/feedback/* faithfully (nothing dropped, nothing invented), routed to the right file, and kept as distilled campaign-agnostic standing guidance (not a verbatim dump).
---

# check-feedback — verify feedback was curated faithfully

Feedback-curation role. After a session, the player's feedback is distilled into the
standing-guidance files under `campaign/feedback/` (one per skill or agent it governs), which those
skills/agents read as binding guidance. Confirm the curation is **faithful to what the player
actually said**, **routed correctly**, and kept as **distilled, campaign-agnostic guidance** — not
dropped, not invented, not a raw paste.

You check fidelity, routing, and distillation — not whether the guidance itself is good advice.
The player's word is the source of truth.

## The checks

### 1. Pull context
- Read the source feedback: the **Player feedback** section of the digest
  `campaign/sessions/session-{N}.md` (the player's words, verbatim) and the session notes
  `campaign/sessions/session-{N}-notes.md` if present. This is the **source of truth** for what the
  player asked for.
- Read the `campaign/feedback/*` files that were created or changed this pass. Read
  `campaign/feedback/README.md` for the routing table (which file governs what).

### 2. Check coverage — every player ask landed
- For each distinct point of player feedback in the source, confirm it is reflected as standing
  guidance in **some** `campaign/feedback/` file. Flag any player ask that didn't land anywhere.
- Genuine non-actionable remarks ("that was fun") need no entry — don't flag those.

### 3. Check fidelity & routing
- For each new or changed guidance entry in a feedback file, confirm it **traces to real player
  feedback** in the source — no invented guidance, no distortion of what the player meant, no
  guidance that contradicts what they asked for. Flag each unsupported or altered entry.
- Confirm each entry sits in the **right file** per the README routing table (e.g. show-don't-tell →
  `social-play.md`, ask-for-rolls → `session-run.md`, pacing → `session-flow.md`). Flag misroutes.
- Confirm each entry **notes the session it came from** (e.g. "(from S{N})"), per the entry format.

### 4. Check it's curated & campaign-agnostic
- **Curated, not dumped:** the feedback file is a tight list of *current* standing guidance, not the
  player's raw verbatim feedback pasted in. Flag a wholesale paste or an entry that just restates the
  transcript instead of stating a general instruction + brief why.
- **Campaign-agnostic:** guidance must name no instance content — no specific NPC, place, item, or
  plot from this campaign. It governs *how the system behaves* in general. Flag any entry that bakes
  in campaign specifics (it belongs in canon, not in guidance).

## Report
Per finding: the issue (**dropped** ask / **invented** or distorted entry / **misrouted** /
**not distilled** / **campaign-specific**), the **source evidence** or the offending file+entry,
and the **fix**.
