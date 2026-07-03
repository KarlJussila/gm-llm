---
name: check-plan
description: The narrative-checker's PRE role — verify a draft session plan against canon, the arc(s) it advances, the registry, and the PC knowledge ledger. Run by the gate before a session plan is finalized.
---

# check-plan — narrative check of a draft session plan

PRE role. The `dm` has handed you a **draft session plan** before it's finalized. Verify it against
canon, the arc(s) it advances, the registry, and the PC's knowledge; the dm fixes the plan from
your list. This is the same fabrication/contradiction check the runtime gate runs, moved one stage
earlier — catch an invented or arc-contradicting identity at planning, before it ever reaches play.

A plan that advances the arc differently than you'd choose is fine — only contradictions,
fabrications, unearned knowledge, overlaps, and blanks are violations.

## The checks

### 1. Pull context — and know what's already loaded
- Read the **draft plan** from your brief. It's there **inline** (the full plan text) or as a
  **path** to read — use whichever your brief gives.
- If your brief contains a **PRE-LOADED CANON** section — a run of `### <path>` blocks — **each block
  is the full, current contents of that file, already read for you** (the INDEX, `state/current.md`,
  the PC ledger, the active arc(s), the entity files the plan named). That header list is the
  definitive set of what's loaded: before you `read`/`grep`/`list`, scan it — **if the file is there,
  use its text from the brief; never re-open it.** Reach for a tool only for something the plan
  references that has **no `### ` block**.
- If your brief has **no** pre-loaded canon block, read canon from disk yourself: the arc(s) it
  advances (`campaign/arcs/{slug}.md` + `.state.md`), `campaign/INDEX.md`, and the PC ledger
  `campaign/characters/{pc}.knowledge.md`.

### 2. Resolve references
- List every entity, place, item, faction, or fact the plan names or relies on.
- For each, locate it in the **INDEX** (the pre-loaded block, or `grep INDEX.md`) and find its file
  — its pre-loaded `### <path>` block if present, else open it. Flag anything that **doesn't
  resolve**, that's a bare `named-only` stub the plan will actually *use* (must be a full file before
  play), or that the plan references without a `[[slug]]` link.

### 3. Honor the arc
- For every identity, reveal, or answer the plan supplies, compare it to the arc's committed
  answers. Flag any that **contradict the arc** or **invent a parallel identity for an already-cast
  NPC** (the arc's intruder is the arc's intruder — not a new name). Name the arc file + beat.
- Confirm the plan actually **pulls** the arc's answers where the session raises those questions,
  rather than re-deciding them.

### 4. Check the ledger
- For every reveal/beat, check the PC ledger + the fact's `[hidden]`/`Known to:` flags. Flag any
  beat that **assumes the PC knows** something they haven't learned, or that mis-flags a reveal
  (known vs. new vs. stays-hidden). Name the source.

### 5. Check for overlap
- For every **newly created** entity in the plan's bundle, cross-reference `INDEX.md` for a
  name/slug collision or a role/function duplicate. Flag each as **merge or differentiate**, naming
  the existing entity's file. (The proactive guard against two near-identical NPCs.)

### 6. Check for blanks
- Scan for any load-bearing fact left unresolved: "DM decides", "TBD", "as needed", "the runner
  creates", a blank identity/reveal. Flag every one — the plan must commit the fact or leave only
  the *player's path* open.

## Report
Per finding: what's wrong; the **correct fact / arc answer** where relevant; the **source file(s)**;
and the **fix instruction** (ground it, pull the arc answer, re-flag, merge/differentiate, fill the
blank).
