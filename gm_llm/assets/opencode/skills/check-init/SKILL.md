---
name: check-init
description: The narrative-checker's INIT role — after all campaign init authoring is complete, verify the full campaign/ directory against the seven-point completeness and consistency checklist.
---

# check-init — verify campaign init

INIT role. Campaign init is complete — world, character, arcs, and state have been authored.
Confirm that **everything is complete, registered, and consistent** before the init commit.

You audit **completeness and consistency**, not design choices.

## The checks

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

## Report
Per finding: what's wrong, which file, and the fix.
