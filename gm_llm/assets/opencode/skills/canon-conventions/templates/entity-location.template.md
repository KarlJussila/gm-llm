---
slug: <kebab-slug, same as the file name>
name: <Canonical Name>
type: location
status: <active | dormant | destroyed | hidden>
summary: <what it is, in one clause>
kind: <tavern, fortress, ruin, shrine, market square, …>
region: <[[region-slug]]>
setting: <the settlement it's in, or its wilderness context>
controlled-by: <[[faction-slug]] or [[npc-slug]], or "unclaimed">
scale: <a single room, a building, a district, a sprawling complex>
---

<!-- Location — what the place truly is. Path: world/locations/{slug}.md. Add {slug}.state.md
     only when the place has live state that changes in play. Fill every <placeholder> with a
     committed value and delete these comments. -->

# <Canonical Name>

## Description
<What it looks, sounds and feels like — enough to set a scene here.>

## Significance
<Why it matters to the campaign; what draws play here.>

## Notable features
<Rooms, landmarks, hazards, defenses — what shapes a scene.>

## Based here
<NPCs and factions who live, work or hold power here, as [[slug]] links. Who is here right now
is state — each one's own `## Location`.>

## Hooks
<Concrete reasons a PC would come or return.>

## Deeper layer / what it hides
<Secret areas, true purpose, what's concealed.>

## Secrets
- [hidden:<secret-id>] <A concealed fact.>
  Known to: <[[slug]], …>

## Links
<[[slug]] references to inhabitants, region, connected places, arcs.>
