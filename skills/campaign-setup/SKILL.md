---
name: campaign-setup
description: Global context for campaign init — read-first guidance and cross-cutting principles for the dm running setup. The orchestrator owns the task sequence; the sub-skills own the per-task work.
---

# campaign-setup

## Read first

Read `campaign/feedback/campaign-setup.md` if it exists — accumulated, player-specific guidance from
past setups. Treat it as binding; let it override the defaults here.

## Principles

- **Meet the player where they are.** Their involvement is set during the brief (free-form vs.
  guided) — when they hand you a dimension, honor it; when they leave it open, decide it well.
- **Spoiler discipline.** In conversation, present setting, tone, and surface situation only. Secrets,
  twists, villains' true natures, and planned arcs go in files, never in what you say to the player.

## Authoring standards

Hold every piece of canon you write to these standards:

- **No blanks.** No "DM decides / TBD / as needed" for any load-bearing fact.
- **Registered.** Every created entity has an `INDEX.md` row.
- **No dangling links.** Every `[[slug]]` resolves; nothing references an unfiled entity.
- **No lingering `named-only`.** Anything the campaign will use is a full file, not a stub.
- **No duplicates.** No new entity overlaps an existing one in name or role.
- **Two-layer + flags.** Hidden truths are committed and flagged `[hidden]` + `Known to:`.
- **Consistent.** Nothing contradicts `campaign.md`, the world, or another file.
