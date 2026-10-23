---
name: feedback-curation
description: Load when folding the player's session feedback into the feedback files.
---

# feedback-curation — turn session feedback into standing guidance

The player's feedback is how the system learns their preferences. Each point becomes durable
guidance in the file for the work it is about, which is handed to that work from then on. This is
curation, not transcription: each file stays a short list of current guidance.

The player's words are under *Player feedback* in the digest, `campaign/sessions/{N}/digest.md`.
The files are in `feedback/`, the player's guidance across all their campaigns, one per audience:
`dm-runner.md` for the table — how sessions are run, narrated, paced and closed — and `dm.md` for
the work between sessions: setup, the world and the story, planning, and your reports.

- **Distil each point** into the behaviour the player wants and a brief why. A remark with nothing
  to act on ("that was fun") needs no entry.
- **Keep it campaign-agnostic.** Name no NPC, place, item or plotline: "Make information hard-won —
  ask for rolls on uncertainty", not "the player wanted a roll to read the Cartographer". A
  campaign specific belongs in canon.
- **Integrate, don't append.** Refine or merge with what the file already says, drop what this
  supersedes, and note the campaign and session each entry came from
  ("(from <campaign> S{N})").

Write only in that directory.
