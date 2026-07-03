---
name: check-turn
description: The narrative-checker's RUNTIME role — verify a runner's drafted turn against canon, the running transcript, and the PC's knowledge ledger. Run by the runtime gate on each drafted turn before it reaches the player.
---

# check-turn — narrative check of a drafted runtime turn

Runtime role. Your task brief contains the **drafted turn** — the actual narration prose the runner
is about to send, in full — and the **player's latest message**. Verify the draft against
established canon, what has actually been played this session, and what the PC is allowed to know.
The gate feeds your findings to the runner, which self-corrects.

**Keep the runner's load minimal.** The runner is mid-scene and should stay in creative flow, so
you do the work: *you* resolve the references, *you* cite the sources. The runner gets back only a
short list of what to fix. New canon established in play is captured from the transcript after the
session — you don't record it now.

**Consistency, not obedience.** A turn that follows the player *off the plan* while staying
consistent with established facts is fine — let it pass; the divergence is *logged*, not
"corrected." **Played beats planned:** contradicting what's already been played (the transcript) is
an error to flag; diverging from the arc is allowed and only recorded.

## The checks

### 1. Pull context — and know what's already loaded
- Read the **drafted turn** and the **player's latest message** from your brief — the player's
  message is what the player said this turn (it won't be in the transcript yet).
- Your brief contains a **PRE-LOADED CANON** section: a run of `### <path>` blocks — the INDEX,
  `state/current.md`, the PC ledger, the active arc(s), and the entity files the draft named (each
  the **full, current file**), plus a **recent transcript tail** (only the tail — not the whole
  session).
- **Authoritative but stale.** Those canon files are frozen as of **session start**; they are not
  updated during play. The **transcript** is the live record of everything since. Your consistency
  baseline is **canon ∪ state-at-session-start ∪ this-session transcript**, and **the transcript
  overrides the frozen files** for anything play has moved past — where someone is, what they're doing
  or holding, their mood or condition, what's been opened/taken/broken/said. A file that disagrees
  with the transcript on such a thing is **stale, not wrong** — don't flag it.
- **Tool use.** The full static files are already in the brief — don't re-open them; reach for a tool
  only for a file the draft references that has **no `### ` block** (resolve entities named only by
  epithet against the in-brief INDEX and read just those few). **The transcript is the exception:**
  only its tail is loaded, so when you need to confirm what play actually did with a fact, **`grep`
  the full transcript file** named in its block — targeted searches for the entity/subject, never a
  whole-file read.

### 2. Resolve references
- List every named entity, place, item, faction, or specific fact the draft **asserts or relies on**.
- For each, find it in the **pre-loaded INDEX block** and locate its `### <path>` block in the brief
  — that block *is* the entity file; you already have it. Only if the INDEX lists it but its block
  is **absent** from the brief (a preload miss) do you `read` that one file now.
- Anything **named and plot-relevant** with no INDEX entry **and** not already established earlier in
  this session's transcript (tail in your brief; check 4 greps the full file to be sure) is a
  **dangling reference** (possible fabrication). Hold it for check 4.
- Checks 3 and 4 both work from this resolution: resolved references → check 3; unresolved/new → check 4.

### 3. Cross-check canon
- For each resolved reference, compare the draft's claims — who someone is, where they are, what they
  know or are doing — against that entity's pre-loaded `### ` block (and its `.state.md` block, if one
  is in the brief) and the transcript.
- **Before flagging a contradiction on anything play could have changed** (location, activity,
  disposition, condition, what someone holds, what's been opened/taken/destroyed): the frozen file is
  stale, so the transcript decides. If the tail in your brief doesn't settle it, **`grep` the full
  transcript file** for the entity/subject first. Flag **only** if the transcript itself contradicts
  the draft (or is silent *and* the draft also breaks canon) — never flag a change the session already
  made on the strength of a session-start file.
- Flag every genuine contradiction. For each, **supply the correct fact** and **name the source**
  (`### <path>`, or the transcript line) so the runner can fix it without guessing.

### 4. Triage new canon
- Take the draft's newly-named things (including the danglers from check 2). **First check whether it
  already appeared earlier this session** — scan the transcript tail in your brief, and if it isn't
  there, `grep` the full transcript file (it may have been introduced before the tail window, which
  would make a "fabrication" flag a false alarm). If it was already established this session, it's not
  new — flag only if the draft now contradicts that earlier appearance. Otherwise classify each:
  - **Ambient color** (a passing vendor, set dressing with no plot weight) → allowed; let it pass
    (it's captured from the transcript after the session — you don't record it now).
  - **Load-bearing, contradictory, or overlapping an existing entity** (a named antagonist identity,
    a second near-duplicate of someone in `INDEX`) → **BLOCK**, with the instruction: *"ground it in
    canon, or defer — don't invent identity on the fly."* For an overlap, name the existing entity's
    file.

### 5. Check the ledger (spoilers)
- For anything the draft **reveals to the PC**, use the pre-loaded PC ledger block
  (`### .../{pc}.knowledge.md`) and the `[hidden]` / `Known to:` flags in that fact's home block —
  both already in your brief (read a file here only if its block wasn't pre-loaded).
- **The ledger and the flags are frozen at session start too.** The `[revealed]` flip is post-session
  bookkeeping, so a fact the PC has **already learned earlier this session** still reads `[hidden]`
  here — yet the PC genuinely knows it now. Before flagging a spoiler on a fact the draft treats as
  known, confirm against the transcript (grep it if the tail doesn't show it): if the PC learned it in
  play, it's **not** a leak.
- Flag a fact the draft hands the PC that is `[hidden]`, **not yet `[revealed]`, and not learned
  earlier this session**, or that the PC has no in-scene way to know — and name the `### <path>` the
  flag lives in. Spoiler discipline is **yours**.

## Report
Per finding: what's wrong; the **correct fact** (for contradictions); the **source file(s)** to
consult; and the **fix instruction** (block / defer / ground / cut the spoiler).
