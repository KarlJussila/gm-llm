---
name: world-build
description: Create and maintain D&D world content — locations, NPCs, factions, and pending world events. Use during campaign initialization and to update world state after sessions. Produces or updates the files under campaign/world/.
---

# world-build

## Player feedback — read first

Before creating or updating world content, read `campaign/feedback/world-build.md` if it exists.
It holds accumulated, player-specific guidance distilled from past sessions. Treat it as binding
and let it override the defaults here wherever they conflict.

Create the living backdrop of the campaign: locations, NPCs, factions, and events. Keep it
consistent with established lore and connected to the campaign's themes. Read the existing
`campaign/world/` files and `campaign/campaign.md` before adding or changing anything.

## Content types

### Locations (`campaign/world/locations.md`)
- Name and description
- Significance — why does this place matter to the campaign?
- Current state — intact, damaged, occupied, abandoned
- Hooks — what draws players here?
- Connections to other locations

### NPCs (`campaign/world/npcs.md`)
- Name, role, appearance
- Personality and mannerisms
- Motivation — what they want and why
- Disposition toward the PCs — friendly, hostile, neutral, complicated
- Secrets — what they know but aren't saying (flag these; see *Awareness flags* below)
- Current situation — what's happening to them right now

### Factions (`campaign/world/factions.md`)
- Name and description
- Goals and methods
- Leader and key members
- Relationship to other factions
- Current activity — what are they doing right now?
- How they might intersect with the PCs

### Events (`campaign/world/events.md`)
Pending world events — things happening whether or not players are present:
- What is happening
- When (in-game time)
- Impact on the world
- How players might learn about it
- How it connects to active arcs

### Significant items (`campaign/world/items.md`)
Campaign-significant objects and artifacts (not mundane gear — that lives on character sheets):
- What it is and why it matters
- Current owner / location
- Current state
- A short history of how its state has changed
During live play `dm-runner` keeps this current; you create or restructure it during init and
post-session world updates. Verbatim text of any written item belongs in `campaign/documents/`.

## Awareness flags

Any secret, hidden motive, true nature, or planned reveal — for an NPC, location, faction, or
item — is **flagged** so the system tracks who knows it (see *Knowledge & awareness* in
`campaign/README.md`):

- Prefix the fact with `[hidden]` (the PC doesn't know) — it becomes `[revealed: S<n>]` once the
  PC learns it.
- Add a `Known to:` line listing the in-world parties aware of it (NPCs, factions, and "the PC"
  once revealed). This is what lets NPCs act only on what they actually know.

Openly apparent details need no flag. Flag the secrets, not the surface. Example:

```
- [hidden] She's an Unbound operative working to accelerate the seal's collapse.
  Known to: Maren, Unbound leadership.
```

## Principles
- **Every location has a hook** — a reason players would go there.
- **Every NPC wants something** — flat NPCs are forgettable.
- **NPCs are not uniformly kind.** Give them friction, suspicion, and personal agendas. Kindness
  is a choice an NPC makes, not a default setting. A stranger's appearance, methods, or
  reputation can and should raise eyebrows. (This mirrors the table craft in `session-run`.)
- **Factions have competing goals** — that's where interesting conflict comes from.
- **The world feels alive** — things happen when players aren't looking.
- **Maintain internal consistency** — don't contradict established facts. Connect to campaign
  themes when possible.

## File output
Update the relevant file(s) under `campaign/world/`. Create the file if it doesn't exist.

## Tone
Make the world feel real and lived-in. Every detail should serve the campaign.
