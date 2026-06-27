---
name: world-build
description: The craft of authoring D&D world content — cosmology, regions, NPCs, factions, locations, and significant items — as layered, living, internally consistent canon. Covers WHAT makes good world content and HOW to design it; the file format/layout/linking is owned by the canon-conventions skill, which you load alongside this. Used during campaign init (world-builder) and when adding world content later (world-keeper).
---

# world-build

## Player feedback — read first

Before creating world content, read `campaign/feedback/world-build.md` if it exists. It holds
accumulated, player-specific guidance distilled from past sessions. Treat it as binding and let it
override the defaults here wherever they conflict.

## Format is not your concern here — load canon-conventions

**Load the `canon-conventions` skill and follow it for all format**: the file layout under
`campaign/`, the entity info/state file pair and their frontmatter, `[[slug]]` linking, the
`INDEX.md` registry, and awareness/`[hidden]` flags. This skill is purely about *what* to author
and *what makes it good*. Where the two overlap, canon-conventions wins on format.

The one rule from there that governs world authoring most: **commit every world-fact now; leave
open only what the player decides.** An NPC's true allegiance, a faction's real goal, the secret a
location holds — decide them at authoring time. Never write "DM decides."

## What the world is made of

- **World truth** (`world/overview.md`, `world/cosmology.md`, `world/history.md`) — non-entity
  setting prose. `overview` is the premise, central conflict, surface situation, themes, and the
  **hidden layer** (what's *really* going on); `cosmology` is how reality works and the truth
  beneath it; `history` is the world's **backstory** — the past that produced the present (distinct
  from the live `state/calendar.md` clock). Non-stateful, not in `INDEX`. Use the `world-overview` /
  `world-cosmology` / `world-history` templates.
- **Regions** (`world/regions/`) — the places at map scale: geography, who holds them, notable
  places within, culture, and **regional history** (a section in the region file, not a separate
  entity), and how they connect.
- **NPCs** (`world/npcs/`) — the people. Each an info/state pair.
- **Factions** (`world/factions/`) — the organizations with goals and reach.
- **Locations** (`world/locations/`) — the specific places play happens.
- **Significant items** (`world/items/`) — campaign-weight objects and artifacts (not mundane
  gear — that lives on the character sheet). Verbatim text of any written item goes in
  `documents/`, referenced from the item file.

## Design in two layers

The strongest world content has a **surface** (what anyone observes) and a **hidden layer** (the
truth beneath). Author both, and flag the hidden parts per canon-conventions §5 (`[hidden]` +
`Known to:`) so the system tracks who knows what.

- **Surface:** the public role, the apparent situation, what a newcomer perceives.
- **Hidden:** the true allegiance, the real motive, the secret the place keeps, the actual cause of
  the visible symptoms. This is where the campaign's tension lives.

Commit the hidden layer to the file even when no one will discover it soon — that's what lets the
runner and the checkers stay consistent, and what stops a downstream agent from inventing a
contradictory "truth."

## Craft principles

- **Every location has a hook** — a concrete reason a player would go there.
- **Every NPC wants something** — a flat NPC is forgettable. Give them an active agenda that
  shapes how they act when the PC isn't steering.
- **NPCs are not uniformly kind.** Kindness is a choice an NPC makes, not a default. Give them
  friction, suspicion, self-interest, and their own agendas. A stranger's manner, methods, or
  reputation can and should raise eyebrows. (Mirrors the table craft in `session-run`.)
- **Factions have competing goals** — overlapping, conflicting aims are where interesting pressure
  comes from. Map how each faction relates to the others and how it might intersect the PC.
- **The world acts on its own.** Things happen whether or not the PC is present. Capture in-motion
  situations and pressures (a faction's plan in progress, a deadline approaching) so the world
  feels alive — and so they can become threads and clocks (`state/threads.md`, `state/clocks.md`).
- **Tie to the campaign's themes.** Every piece should serve what the campaign is *about*.
- **Stay internally consistent.** Read existing world files and `campaign.md` before adding
  anything; never contradict established canon. Check `INDEX.md` before creating an entity so you
  reuse what exists instead of spawning a near-duplicate.

## What "good" looks like when you're done

- Each entity reads as a real, motivated presence with a surface and a committed hidden layer.
- Every load-bearing fact is decided — no blanks, no "DM decides."
- Everything is registered, linked, and format-clean per canon-conventions.
