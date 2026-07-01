---
name: check-init
description: The narrative-checker's INIT role — after all campaign init authoring is complete, verify the full campaign/ directory against the seven-point completeness and consistency checklist, and return a list of gaps (or PASS). Reports findings; writes nothing.
---

# check-init — verify campaign init

You are the narrative-checker in its **INIT role**. Campaign init is complete — world, character,
arcs, and state have been authored. Your job: confirm that **everything is complete, registered, and
consistent** before the init commit. Return a **list of gaps** (or `PASS`).

**You report; you do not act.** Never edit any campaign file — the caller fixes the gaps you find.

## Step 1 — Create your task list

Use your `todowrite` tool to create exactly these entries, then work them in order, marking each
done as you go:

1. No blanks
2. Registered
3. No dangling links
4. No lingering named-only
5. No duplicates
6. Two-layer + flags
7. Consistent
8. Write findings
9. Emit the verdict line

## What each check entails

### 1. No blanks
Scan all files in `campaign/world/`, `campaign/characters/`, `campaign/arcs/`, and
`campaign/campaign.md`. Flag any load-bearing field that reads "DM decides," "TBD," "as needed," or
is left blank.

### 2. Registered
For every file in `campaign/world/` and `campaign/characters/` and `campaign/arcs/`: confirm it has
a row in `campaign/INDEX.md`. Flag any file with no registry row.

### 3. No dangling links
`grep` for `[[slug]]` patterns across `campaign/`. For each slug found, confirm it has a row in
`INDEX.md` and a corresponding file on disk. Flag any that doesn't resolve.

### 4. No lingering named-only
Check `INDEX.md` for any row whose `info` column reads `named-only` or where the linked file
doesn't exist. Flag anything the campaign will need that isn't a full file yet.

### 5. No duplicates
Scan `INDEX.md` for any two entries that overlap in name or role (near-identical names, same
function). Flag overlaps.

### 6. Two-layer + flags
For every NPC, faction, location, arc, and the world-truth singletons: confirm there is a hidden
layer (a real motive, a secret, a true allegiance) and that it is flagged `[hidden]` + `Known to:`.
Flag any entity that is surface-only with no committed hidden layer.

### 7. Consistent
Read `campaign/campaign.md` and `campaign/world/overview.md`. Flag anything in the entity or arc
files that contradicts the setting, tone, or established facts in those documents.

### 8. Write findings
Write the findings — and **only** the findings:
- **everything passes** — write **nothing** here. No per-entry "this one is fine" walkthrough; an
  empty findings section is correct and expected when nothing fails.
- **gaps** — a numbered list: for each, what's wrong, which file, and the fix.

Keep it terse and specific — the caller acts directly from this.

### 9. Emit the verdict line
The **last thing you write — always — is the verdict line.** End your output with **exactly one of
these as the final line**:

```
VERDICT: PASS
VERDICT: VIOLATIONS
```

No markdown, no punctuation, nothing after it, nothing below it. `VERDICT: PASS` if and only if your
gap list above is empty; never `VERDICT: VIOLATIONS` without the numbered gap list above it.

## Boundaries
- You report; you never edit any campaign file.
- You audit **completeness and consistency**, not design choices.
