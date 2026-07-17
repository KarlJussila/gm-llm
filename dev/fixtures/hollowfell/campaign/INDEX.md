/*
  The registry / slug resolver. Path: campaign/INDEX.md
  Three jobs: dedup guard, slug->file resolver, inventory (canon-conventions §6).
  Every named entity gets a row — including named-only stubs with no file yet (a mid-session
  tolerance only; whoever is authoring canon turns every named-only into a full file, same pass).
  Registered: NPCs, factions, locations, regions, items, concepts, bestiary creatures, arcs. NOT
  registered: the world-truth singletons (overview/cosmology/history) and state/* docs (fixed paths),
  nor clocks/threads.
  One table per type. Keep one-line entries to a single clause.
*/
# INDEX — Campaign Registry

## PC
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| dallid | Dallid | active | characters/dallid.md | characters/dallid.state.md | Vedalken wizard; brilliant biomancer searching for his missing mentor |

## NPCs
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| seraphine-duskward | Seraphine Duskward | active | world/npcs/seraphine-duskward.md | world/npcs/seraphine-duskward.state.md | First Warden of the Concordance; pragmatic investigator |
| thaleus-venn | Thaleus Venn | active | world/npcs/thaleus-venn.md | world/npcs/thaleus-venn.state.md | Concordance researcher; the only person studying the Lattice |
| vashra-keel | Vashra Keel | active | world/npcs/vashra-keel.md | world/npcs/vashra-keel.state.md | Covenant field commander; ruthless suppressor of dangerous knowledge |
| erasmus-venn | Erasmus Venn | hidden | world/npcs/erasmus-venn.md | world/npcs/erasmus-venn.state.md | Former Academy researcher; Dallid's missing mentor |
| maret | Maret | active | world/npcs/maret.md | world/npcs/maret.state.md | Tavern keeper at the Rusty Anchor, Greyhaven |
| brennan-cole | Brennan Cole | active | world/npcs/brennan-cole.md | world/npcs/brennan-cole.state.md | Foreman at Hollowfell Mine; over his head and knows it |
| wren | Wren | active | world/npcs/wren.md | world/npcs/wren.state.md | Concordance field investigator; Seraphine's recruit |
| tarin | Tarin | active | world/npcs/tarin.md | world/npcs/tarin.state.md | Missing miner; transported to the Ashenmere Wastes by the Lattice node |

## Factions
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| aetherial-concordance | The Aetherial Concordance | active | world/factions/aetherial-concordance.md | world/factions/aetherial-concordance.state.md | Ancient order sworn to protect reality's foundations |
| covenant-of-the-sealed-veil | The Covenant of the Sealed Veil | active | world/factions/covenant-of-the-sealed-veil.md | world/factions/covenant-of-the-sealed-veil.state.md | Secret society that believes dangerous knowledge must be destroyed |
| unraveler | The Unraveler | active | world/factions/unraveler.md | world/factions/unraveler.state.md | Hidden antagonist exploiting the Primordial Lattice |

## Locations
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| greyhaven | Greyhaven | active | world/locations/greyhaven.md | world/locations/greyhaven.state.md | Market town in the Thornmere Marches; the campaign's home base |
| the-concordance-bastion | The Concordance Bastion | active | world/locations/the-concordance-bastion.md | world/locations/the-concordance-bastion.state.md | Concordance regional headquarters in the capital |
| the-briarwood | The Briarwood | active | world/locations/the-briarwood.md | world/locations/the-briarwood.state.md | Ancient bramble forest with temporal disturbances |
| hollowfell-mine | Hollowfell Mine | active | world/locations/hollowfell-mine.md | world/locations/hollowfell-mine.state.md | Mine where magic fails; sits on a Lattice node |
| luminarch-academy | The Luminarch Academy | active | world/locations/luminarch-academy.md | world/locations/luminarch-academy.state.md | Continent's foremost institution of magical learning |
| high-thorn-fortress | High Thorn Fortress | active | world/locations/high-thorn-fortress.md | — | Crown's military stronghold on the northern border |
| the-ashford-court | The Ashford Court | active | world/locations/the-ashford-court.md | — | Capital city of the Crown of Thorns |
| the-bone-gardens | The Bone Gardens | active | world/locations/the-bone-gardens.md | — | Petrified formations in the Ashenmere Wastes |
| the-convergence-point | The Convergence Point | active | world/locations/the-convergence-point.md | — | Epicentre of the Sundering; no one has reached it in living memory |

## Regions
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| thornmere-marches | The Thornmere Marches | active | world/regions/thornmere-marches.md | world/regions/thornmere-marches.state.md | Frontier province of marshes and bramble; the campaign's starting region |
| ashenmere-wastes | The Ashenmere Wastes | active | world/regions/ashenmere-wastes.md | world/regions/ashenmere-wastes.state.md | Blighted scar of the Sundering; ungoverned and hostile |
| crown-of-thorns | The Crown of Thorns | active | world/regions/crown-of-thorns.md | world/regions/crown-of-thorns.state.md | Kingdom of fertile heartlands; the dominant political power |

## Items
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|

## Concepts
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| primordial-lattice | The Primordial Lattice | active | world/concepts/primordial-lattice.md | — | Hidden architecture underlying all of reality |
| the-sundering | The Sundering | active | world/concepts/the-sundering.md | — | Catastrophic magical disaster that shaped the present age |

## Bestiary
/* Generic, reusable creature TYPES (goblin, wolf, guard) — single stateless files, no state column.
   A named/unique creature is an NPC above, not here. */
| slug | name | file | one-line |
|---|---|---|---|

## Arcs
| slug | name | tier | status | design | state | one-line |
|---|---|---|---|---|---|---|
| the-unraveling | The Unraveling | major | dormant | arcs/the-unraveling.md | arcs/the-unraveling.state.md | Dallid's search for Erasmus leads to the truth about the Lattice and the Unraveler |
| the-hollowfell-investigation | The Hollowfell Investigation | minor | dormant | arcs/the-hollowfell-investigation.md | arcs/the-hollowfell-investigation.state.md | Investigating a mine where magic fails reveals the first evidence of deliberate Lattice manipulation |
