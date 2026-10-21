---
name: check-init
description: Load when reviewing the authored campaign before its first session.
---

# check-init

The code has checked layout, frontmatter, links, secret ids, arc coverage and initial state.
Review the campaign's meaning:

- Look for entities that duplicate another's name or role and should be one entity.
- Every entity, arc and world-truth document needs a committed hidden layer: a motive, allegiance,
  secret or underlying truth that gives its surface meaning. Flag surface-only content.
- Compare the world, PC and arcs with `campaign/campaign.md` and each other. Flag contradictions
  in facts, tone, themes or the player's content boundaries.

Report each gap with its file, what conflicts or is missing, and the correction it needs.
