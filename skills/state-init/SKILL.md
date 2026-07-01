---
name: state-init
description: Initialize all campaign state as of session 1 — entity and arc snapshots, the opening scene, calendar, active threads, and clocks. Loaded by the dm at campaign init after arcs are designed. Task-list-first.
---

# state-init

## Build your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Write entity and arc state files
2. Write `state/current.md`
3. Write `state/calendar.md`
4. Write `state/threads.md`
5. Write `state/clocks.md`
6. Verify

## Steps

### 1. Write entity and arc state files
For every stateful entity and every arc, write `{slug}.state.md` (`as-of: S1`) from its starting
facts: location/condition/what it's doing; arcs at their starting status (usually `dormant`).

### 2. Write `state/current.md`
The opening scene: where the PC is, when, who's present, the immediate situation, and the opening
hook. This is the runner's resume baseline.

### 3. Write `state/calendar.md`
The campaign's start date and any fixed calendar reference.

### 4. Write `state/threads.md`
The leads the PC starts with (from backstory and opening hooks).

### 5. Write `state/clocks.md`
Any time-pressure an arc set in motion at the start.

### 6. Verify
`INDEX.md` lists every entity; no `[[slug]]` dangles; nothing reads `named-only`.
