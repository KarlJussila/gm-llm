---
name: check-propagation
description: The narrative-checker's POST role — after a session's updates have been applied, verify that everything from the session digest propagated correctly into canon and state (ledger flips, new-canon files + registry rows, state snapshots, arc bodies, documents).
---

# check-propagation — verify the apply pass propagated everything

POST role. You're given a session number, after that session's updates have been applied to canon
and state. Confirm that **everything the session established actually landed** — nothing dropped.
The core risk you guard against: a named, load-bearing thing established in play must not silently
vanish before it's filed.

You audit **propagation**, not design: you're not re-judging the authoring choices, only whether
every established fact made it from the record (the digest) into canon and state.

## The checks

### 1. Pull context
- Read the digest `campaign/sessions/session-{N}.md` — the structured extraction of what was played.
  It is your **single source-of-truth record** for what the session established.
- Read `campaign/INDEX.md` and the updated files (entity info/state, arcs, ledger, `state/*`,
  `documents/`). You're checking the digest (the record) against the updated canon (what landed).

### 2. Check new canon filed
- For every **new or changed NPC/location/faction/event** in the digest's *World canon* section
  (including anything the DM improvised): confirm it now has an `INDEX.md` row **and** a real file (a
  load-bearing one a full file, not a lingering `named-only`). Flag any that's still unfiled or
  stub-only.
- For every **plan/arc divergence** in the digest's *Plan vs. actual* section: confirm it's reflected
  in the arc body/`.state.md` (the body was actually revised, not just a status bump). Flag any
  divergence left unreconciled.

### 3. Check ledger propagation
- For every reveal in the digest (something the PC learned): confirm the fact's home file flipped
  `[hidden]` → `[revealed: S{N}]` with `Known to:` updated, **and** a matching line was added to
  `campaign/characters/{pc}.knowledge.md`. Flag any reveal that updated only one layer or neither.

### 4. Check state propagation
- For every entity whose situation changed in play (per the digest): confirm its `.state.md` was
  updated to `as-of: S{N}`. Confirm `state/current.md` reflects the new scene, `state/calendar.md`
  advanced, and any new/closed `threads`/`clocks` were applied. Flag stale snapshots.

### 5. Check registry integrity
- `grep` for `[[slug]]` links across `campaign/` and confirm each resolves in `INDEX.md`; confirm
  every `INDEX.md` row points at a file that exists on disk (and vice-versa — no orphan files).
  Flag dangling links and registry/disk mismatches.

## Report
Per finding: what's missing, the **source** (which digest entry it came from), the **target file**
that should have it, and the **fix** (file the entity, flip the flag, update the snapshot, revise
the arc body, fix the link).
