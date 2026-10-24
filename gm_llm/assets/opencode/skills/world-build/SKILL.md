---
name: world-build
description: Load when authoring or revising the world, its entities or its underlying truths.
---

# world-build

What to author and what makes it good; `canon-conventions` owns the format.

## Building a new world

Build it top down, each tier to its own depth, so that where the PC begins sits inside a world
already thought through, and the player meets its details close up.

- **The world, in broad strokes.** Its countries and powers and where they stand with each other,
  its important cities, the factions that cross borders, its peoples, its faiths and gods, and what
  magic means in ordinary life. A history with named eras and events that explains today's map. A
  name, what it wants and a paragraph is enough for most of it.
- **The region, in structure.** Its geography: terrain, rivers and roads, and how long the roads
  take. Its settlements by name. Who holds power, who contests it, and how it is governed. Its
  neighbours, and the dangers in its wild places.
- **The vicinity, in fine detail.** Where the PC begins is a place to live in: the people they would
  deal with — whoever runs things, keeps the inn, holds the local office, a rival, a friend — each
  named and wanting something; places to go, each with a hook; what is going on there now; and
  problems of its own beside the main story.

The main story runs through all three, but the world does not exist to serve it: most of what the
player meets is simply the world going about its business.

## What the world is made of

- **World truth** — `world/overview.md` (premise, central conflict, surface situation, themes and
  what's really going on), `cosmology.md` (how reality works, its powers and faiths, and the truth
  beneath them) and `history.md` (the past that produced the present). Setting prose, not entities.
- **Regions** — places at map scale: geography, who holds them, the places within, culture, how
  they connect, their history.
- **NPCs**, **factions** with goals and reach, and **locations** where play happens. Any of them
  the story is likely to reach gets a file; `create_entities` writes many at once.
- **Significant items** — campaign-weight objects, not mundane gear, which lives on the character
  sheet. The verbatim text of a written item goes in `documents/`.
- **Concepts** — load-bearing ideas that aren't people, places, organizations or objects: a
  cosmological force, a cataclysm, a magic system. Give one its own file once other canon needs to
  link it, rather than burying it in cosmology or history.

## Two layers

Strong world content has a surface — the public role, the apparent situation, what a newcomer sees —
and, where something is concealed, a hidden layer: the true allegiance, the real motive, the secret a
place keeps, the actual cause of the visible symptoms. That's where the tension lives. Write it into
the file, tagged as `canon-conventions` says, even when no one will find it soon: it keeps the runner
and the checks consistent and stops a later author inventing a contradictory truth. Not everything
has one; the baker can just be the baker.

## Craft

- **Every location has a hook** — a concrete reason to go there.
- **Every NPC wants something**, and pursues it when the PC isn't steering. Kindness is a choice,
  not the default: give them friction, suspicion and self-interest.
- **Factions have competing goals.** Overlapping, conflicting aims are where pressure comes from; map
  how each relates to the others and might cross the PC.
- **The world acts on its own.** Capture situations in motion — a plan under way, a deadline closing
  in — so they can become threads and clocks.
- **Serve the themes.** Every piece should serve what the campaign is about.
- **Stay consistent.** Read `campaign.md` and the existing world before adding to it, and check
  `INDEX.md` so you reuse what exists instead of making a near-twin.
