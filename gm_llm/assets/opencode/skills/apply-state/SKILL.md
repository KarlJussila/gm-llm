---
name: apply-state
description: Load when bringing the knowledge ledger and the state files up to the end of a played session.
---

# apply-state — bring the "now" up to date

Canon says who things are; state says where they stand now. After a session, state catches up to
what play changed, each file written as true at the end of this session. The record is the digest,
`campaign/sessions/{N}/digest.md` — chiefly *Knowledge gained*, *Secrets & awareness*, *Character
state* and *Narrative*. `canon-conventions` is the format, and its *What goes where* says which
file each fact belongs in.

## The knowledge ledger

Add to `characters/{pc}.knowledge.md` everything the PC learned, deduced or was told: what it now
knows, what it believes (mark the false beliefs) and the open questions it became aware of.

When what it learned is a tagged secret, end the ledger line with `[learned:<id> S{N}]`. That is
the whole reveal: the orchestrator turns the home tag into `[revealed:<id> S{N}]` and adds the PC to
its `Known to:`. When an NPC learned something, add them to that secret's `Known to:` yourself.

## Snapshots

Every entity whose situation play changed, and every one newly introduced, gets its `.state.md`
rewritten as of this session: where it is, its disposition toward the PC, its condition and what
it means to do next, with `as-of: S{N}`. The PC's own state file too. Keep each short; state is the
now, not the history, and never HP, slots or coin.

A place's state is the place's own: what has changed there. Someone arriving, staying or leaving is
their own `## Location`, not something that happened to the place.

## The dashboards

- `state/current.md` — the scene and situation the session ended on: where the next one opens.
- `state/calendar.md` — the in-game date advanced, and the session's dated events.
- `state/clocks.md` — clocks ticked, added or resolved as play moved them.

## Scope

The knowledge ledger, `Known to:` lines for NPCs, every `.state.md`, and those three dashboards.
Arcs (their state files included) and `state/threads.md` were reconciled in the arc step.
