The session is over. Before your context is gone, write handoff notes for the between-session pipeline — the record of what actually happened that the campaign manager will fold into canon and use to plan the next session. You have the whole session fresh in mind; capture what a reader of the bare transcript might miss.

This is an internal note to the campaign team, not a message to the player — be direct and specific, name names, and don't worry about spoilers.

Cover, in whatever order fits what happened (skip a heading if nothing applies):

- **Story trajectory** — how the arcs and open threads moved, what shifted the situation, and where things are pointed now. Note any clock that advanced or should.
- **New entities** — every NPC, location, faction, or item that first appeared or was named this session, with a one-line note on each so it can be filed. Nothing that came up should stay unfiled.
- **Changed entities** — anyone/anywhere already in canon whose state, disposition, or situation changed, and how.
- **The character** — what the PC did, learned, gained or lost, and any development worth recording.
- **Loose ends** — unresolved questions, promises made, hooks left dangling, and anything you set up that expects a payoff.

Deliver the notes the same way you ended the session: call `task_complete` with the complete notes in its `notes` argument. That argument is the only channel the orchestrator files — prose you type as a reply is not captured — so put the full text there, not a summary of it.