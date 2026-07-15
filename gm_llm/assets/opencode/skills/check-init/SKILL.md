---
name: check-init
description: The narrative-checker's INIT role — after all campaign init authoring is complete, verify the full campaign/ directory against the seven-point completeness and consistency checklist.
---

# check-init — verify campaign init

INIT role. Campaign init is complete — world, character, arcs, and state have been authored.
Confirm that **everything is complete, registered, and consistent**.

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
`INDEX.md` and a corresponding file on disk. Flag any that doesn't resolve. The fix you prescribe
is always both halves: author the **complete entity file** from its `canon-conventions` template
*and* register it in `INDEX.md`. At init there is no `named-only` tolerance — that is a mid-session
allowance only. Never prescribe an index row alone, a stub, or file creation as "optional."

### 4. No lingering named-only
Check `INDEX.md` for any row whose `info` column reads `named-only` or where the linked file
doesn't exist. Flag every one. At init, anything named anywhere in `campaign/` gets a full file —
there is no "index row only" state and no judgment call about what the campaign will need.

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
Per finding: what's wrong, which file, and the fix. For any missing or unfiled entity, the fix is
always the same and never softened: author the complete file from its template and register it.
Nothing at init is optional, deferred, or "if needed."
