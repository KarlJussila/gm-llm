---
name: apply-state
description: The post-session state pass — flip the knowledge ledger and reveal flags for what the PC learned, and update every state snapshot (entity .state.md, state/current, state/calendar, state/clocks) to where things stand after the session. Loaded by the dm during the post-session apply, once the digest exists.
---

# apply-state — bring the mutable "now" up to date

Canon says who things *are*; **state** says where they stand *now*. After a session, the live record
has to catch up to what play changed: what the PC has learned, and where every moving piece now
stands as of this session boundary.

## Format is a contract — load canon-conventions
Load `canon-conventions` and follow it for the info/state pair, the `[hidden]` → `[revealed: S<n>]`
flag convention with `Known to:`, the PC knowledge ledger, and the `state/*` dashboards. State files
are **session-boundary snapshots** — write each as true *as of the end of this session*.

## Input
- The **session digest** `campaign/sessions/session-{N}.md` — especially *Knowledge gained*,
  *Secrets & awareness*, *Character state*, and *Narrative* (for the closing scene).
- The **PC knowledge ledger** `campaign/characters/{pc}.knowledge.md`, the entity `.state.md` files,
  and `state/current.md`, `state/calendar.md`, `state/clocks.md`.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Update the knowledge ledger and flip reveals
2. Update entity state snapshots
3. Update the global state dashboards
4. Self-check
5. Report

### 1. Update the knowledge ledger and flip reveals
- For everything the PC learned, deduced, or was told this session (digest *Knowledge gained* /
  *Secrets & awareness*): add it to `characters/{pc}.knowledge.md` — what they now know, believe
  (mark beliefs that are false), and the open questions they became aware of.
- For each revealed secret whose home is an entity file, flip its flag `[hidden]` →
  `[revealed: S{N}]` and update `Known to:`. If an NPC learned something, update who-knows-what too.
- The ledger and the flags are mirrors: every reveal updates both.

### 2. Update entity state snapshots
For each entity whose situation changed in play (and each newly introduced one), write its
`{slug}.state.md` as of this session boundary: current location, disposition toward the PC,
condition, and immediate intent. Keep it short — state is the now, not the history. Don't track
granular mechanical resources; record only narratively significant state.

### 3. Update the global state dashboards
- `state/current.md` — the new "you are here": the scene/situation play left off at, the resume
  pointer for next session.
- `state/calendar.md` — advance the in-game date and log the session's dated events.
- `state/clocks.md` — tick, add, or resolve the time-pressure clocks per what play moved.

### 4. Self-check
- The ledger reflects everything the PC learned, and every matching source flag was flipped.
- Every entity whose situation changed has a fresh `as-of: S{N}` snapshot.
- `current` / `calendar` / `clocks` reflect where the session left things.

### 5. Report
Brief: **Result** (ledger + snapshots updated), **Caveats** (anything the digest left ambiguous).

## Boundaries
- Your scope is **the PC knowledge ledger, reveal flags in entity files, every `.state.md`, and
  `state/current` / `state/calendar` / `state/clocks`**. Leave entity canon (who things are) and the
  arcs + threads to their own reconciliation — your job here is the live state.
