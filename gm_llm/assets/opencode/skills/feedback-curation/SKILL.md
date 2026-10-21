---
name: feedback-curation
description: Load when folding the player's session feedback into the feedback files.
---

# feedback-curation — turn session feedback into standing guidance

The player's feedback is how the system learns their preferences. Each point becomes durable
guidance in the file that governs the behaviour it is about, so that skill or agent reads it next
time. This is curation, not transcription: each file stays a short list of current guidance.

The player's words are under *Player feedback* in the digest, `campaign/sessions/{N}/digest.md`.
The files are in the `feedback-dir` named in `gm-llm.yaml`, shared by all the player's campaigns:
`<skill-name>.md` for behaviour a skill governs, otherwise `<agent-name>.md` — `dm-runner.md` for
live play, `dm.md` for setup conversation and your reports.

- **Distil each point** into the behaviour the player wants and a brief why. A remark with nothing
  to act on ("that was fun") needs no entry.
- **Keep it campaign-agnostic.** Name no NPC, place, item or plotline: "Make information hard-won —
  ask for rolls on uncertainty", not "the player wanted a roll to read the Cartographer". A
  campaign specific belongs in canon.
- **Integrate, don't append.** Refine or merge with what the file already says, drop what this
  supersedes, and note the campaign and session each entry came from
  ("(from <campaign> S{N})").

Write only in that directory.
