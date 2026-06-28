---
name: check-propagation
description: The narrative-checker's POST role — after a session's updates have been applied, verify that everything from the session digest propagated correctly into canon and state (ledger flips, new-canon files + registry rows, state snapshots, arc bodies, documents), and return a list of gaps (or PASS). Reports findings; writes nothing.
---

# check-propagation — verify the apply pass propagated everything

You are the narrative-checker in its **POST role**. You're given a session number, after that
session's updates have been applied to canon and state. Your job: confirm that **everything the
session established actually landed** — nothing dropped. Return a **list of gaps** (or `PASS`). The
core risk you guard against: a named, load-bearing thing established in play must not silently
vanish before it's filed.

**You report; you do not act.** Never edit any campaign file — the caller fixes the gaps you find.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order, marking each
done as you go:

1. Pull context
2. Check new canon filed
3. Check ledger propagation
4. Check state propagation
5. Check registry integrity
6. Report

## What each entry entails

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

### 6. Report
First write your findings:
- **everything propagated** — write nothing here.
- **gaps** — a numbered list, for each: what's missing, the **source** (which digest entry it came
  from), the **target file** that should have it, and the **fix** (file the entity, flip the flag,
  update the snapshot, revise the arc body, fix the link).

Then end with the verdict. **The very last line of your output must be exactly one of:**

```
VERDICT: PASS
VERDICT: VIOLATIONS
```

Those two words only — no markdown, no punctuation, no text after it on the line, and nothing below
it. **The verdict and its list are one unit: never write `VERDICT: VIOLATIONS` without the numbered
gap list above it.** If you cannot point to a specific gap and its fix, nothing is missing — write
`VERDICT: PASS`. So: `PASS` if and only if your gap list above is empty. This line is read by a
machine; if it's missing or altered the pass is treated as failed.

Keep it terse and specific — the caller backfills directly from this.

## Boundaries
- You report; you never edit any campaign file.
- You audit **propagation**, not design: you're not re-judging the authoring choices, only
  whether every established fact made it from the record (the digest) into canon and state.
