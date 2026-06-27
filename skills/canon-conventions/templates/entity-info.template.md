<!--
  Entity INFO file — static canon. One per stateful entity, paired with {slug}.state.md.
  Path: world/{npcs|factions|locations|items}/{slug}.md
  Fill every <placeholder>; delete sections that don't apply to this entity type.
  Adapt section names by type (see canon-conventions §3): NPC uses Personality;
  faction uses Goals & methods; location/item uses Description & significance.
-->
---
slug: <kebab-slug>
name: <Canonical Name>
type: <npc | faction | location | item | region>
status: <active | dormant | dead | destroyed | hidden | named-only>
---

# <Canonical Name>

## Identity / Public role
<What is openly apparent — what anyone in the world would observe or know.>

## Personality / mannerisms        <!-- NPC; for faction use "Goals & methods", for place/item "Description & significance" -->
<How they present and behave / what the faction pursues and how / what the place or item is and why it matters.>

## Deeper layer / true nature
<The real story: hidden allegiances, true purpose, what's actually going on beneath the surface. Commit it now — no "DM decides".>

## Agenda / what they want
<The active want that drives them. Flat entities are forgettable.>

## What they know
<Facts this entity is aware of — this gates how they can act. Reference other entities/facts with [[slug]] links.>

## Disposition toward the PC
<Friendly / hostile / wary / transactional / complicated — and why.>

## Secrets
<!-- Flag the secrets, not the surface (canon-conventions §5). -->
- [hidden] <A concealed fact.>
  Known to: <[[slug]], faction, …>

## Links
<[[slug]] references to related entities, factions, locations, arcs, threads. Link first mention.>
