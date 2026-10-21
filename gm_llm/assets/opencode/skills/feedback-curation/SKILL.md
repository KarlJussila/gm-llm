---
name: feedback-curation
description: Load when folding the player's session feedback into the feedback files.
---

# feedback-curation — turn session feedback into standing guidance

The player's feedback is how the system learns their preferences. Each point becomes durable
guidance in the file that governs the behaviour it is about, so that skill or agent reads it next
time. This is curation, not transcription: each file stays a short list of current guidance.

The player's words are under *Player feedback* in the digest, `campaign/sessions/{N}/digest.md`.
The routing table and entry format are in `campaign/feedback/README.md`.

- **Distil each point** into the behaviour the player wants and a brief why. A remark with nothing
  to act on ("that was fun") needs no entry.
- **Keep it campaign-agnostic.** Name no NPC, place, item or plotline: "Make information hard-won —
  ask for rolls on uncertainty", not "the player wanted a roll to read the Cartographer". A
  campaign specific belongs in canon.
- **Integrate, don't append.** Refine or merge with what the file already says, drop what this
  supersedes, and note the session each entry came from ("(from S{N})").

Write only under `campaign/feedback/`.
