<!--
  The registry / slug resolver. Path: campaign/INDEX.md
  Three jobs: dedup guard, slug->file resolver, inventory (canon-conventions §6).
  Every named entity gets a row — including named-only stubs with no file yet.
  Registered: NPCs, factions, locations, regions, items, arcs. NOT registered: the world-truth
  singletons (overview/cosmology/history) and state/* docs (fixed paths), nor clocks/threads.
  One table per type. Keep one-line entries to a single clause.
-->
# INDEX — Campaign Registry

## NPCs
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | world/npcs/<slug>.md | world/npcs/<slug>.state.md | <who, in one clause> |

## Factions
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | world/factions/<slug>.md | world/factions/<slug>.state.md | <what, in one clause> |

## Locations
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | world/locations/<slug>.md | world/locations/<slug>.state.md | <what, in one clause> |

## Regions
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | world/regions/<slug>.md | <— unless control is contested> | <what, in one clause> |

## Items
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | world/items/<slug>.md | <— if not stateful> | <what, in one clause> |

## Arcs
| slug | name | status | design | state | one-line |
|---|---|---|---|---|---|
| <slug> | <Name> | <status> | arcs/<slug>.md | arcs/<slug>.state.md | <the arc's premise, in one clause> |
