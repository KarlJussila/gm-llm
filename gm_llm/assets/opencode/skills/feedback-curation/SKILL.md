---
name: feedback-curation
description: Use when folding the player's session feedback into standing guidance.
---

# feedback-curation

The player's words are under Player feedback in `campaign/sessions/{N}/digest.md`. Write guidance
in the player feedback directory configured by `feedback-dir` in `gm-llm.yaml`, shared across
campaigns. Relative paths start at the project root; `~` is the user's home.

Distil each actionable point into the behaviour the player wants and a brief why. Keep it
campaign-agnostic: preferences go here; facts about this campaign belong in canon. Integrate with
the current guidance, merge duplicates and remove what the new feedback supersedes.

Use one `<skill-name>.md` per skill. Put conduct governed by an agent's prompt in `<agent-name>.md`.
In particular, live narration, agency, rolls, spoilers, opening and pacing belong in `dm-runner.md`;
closing and feedback collection belong in `session-close.md`; setup conversation and the campaign
manager's reports belong in `dm.md`. Prefer a skill file when a skill owns the behaviour.

Note the source campaign and session beside each entry so sessions from different campaigns stay
distinguishable. Each file is a short list of current guidance, not a transcript or history.
