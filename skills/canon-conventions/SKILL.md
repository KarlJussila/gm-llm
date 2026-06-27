---
name: canon-conventions
description: The shared house style for writing campaign canon — file layout, entity info/state file pairs and frontmatter, slug naming, [[slug]] linking, the INDEX registry, awareness/hidden flags, and the "commit every fact, never say DM decides" authoring rule. Load this whenever you author or edit any file under campaign/ so every writer stays consistent in *how* canon is recorded.
---

# canon-conventions

This is the **format contract** every canon-writing agent shares. It governs *how* the campaign is
recorded — file layout, naming, linking, frontmatter — so that the dm — authoring world, arcs,
entities, plans, and state — writes the same shape of file every time and never drifts. *What* to write is each agent's own job; *how* to write it is here.

Read this before authoring or editing anything under `campaign/`. When this skill and an agent's
own prompt both speak to format, this skill wins.

**Templates and a worked example ship alongside this skill.** Copy from `templates/` and fill every
`<placeholder>`, deleting the `<!-- guidance -->` comments. There is one template per shape:
- **Typed entity info** — `entity-npc`, `entity-faction`, `entity-location`, `entity-item`,
  `entity-region` (each type has a different body; pick the matching one).
- **`entity-state`** — one shared state shape for every stateful entity.
- **World-truth docs** — `world-overview`, `world-cosmology`, `world-history` (non-entity setting
  prose; see §3).
- **`INDEX`**, the four **`state/*`** docs, and the **session deltas** log.

See `examples/` for a complete filled entity pair (`lysa-fenn.md` + `.state.md`) and a sample
`INDEX.md` — the generic illustrative cast there carries through this skill's examples too.

---

## 1. The one authoring rule

> **Commit every world-fact at authoring time. Leave open only what the player decides.**

Whenever you write canon, the *facts* are fixed now: an NPC's true identity, what they know, the
answer behind a mystery, what a search turns up, who the intruder actually is. The only legitimate
blank is the **player's path** — their choices, and the situations they choose among.

- **Never write "DM decides," "the runner creates," "as needed," "TBD,"** or any other punt for a
  load-bearing fact. That punt is exactly what lets a downstream agent fabricate a contradiction.
  If canon already answers the question, pull that answer; if it doesn't, **decide it now** and
  file it.
- **Threshold — load-bearing vs. ambient.** This rule binds *load-bearing* facts: identities, what
  an NPC reveals, the resolution of a mystery, the consequence of a check, anything the plot leans
  on. Trivial ambient color (a passing vendor's name, the weather) is the runner's to improvise at
  the table and gets logged then — don't pre-author it.

Everything else in this skill is machinery for recording committed facts consistently.

---

## 2. File layout

Everything lives under `campaign/`. Static truth and live state are distinguished by a **filename
suffix** (`.state.md`) and the registry — *not* by a top-level split, so an entity's info and state
files sit side by side.

```
campaign/
├── INDEX.md                         # the registry / slug resolver (see §6)
├── campaign.md                      # premise, spoiler-free pitch
├── world/
│   ├── overview.md  cosmology.md  history.md   # world-truth singletons (no slug, no .state.md, not in INDEX)
│   ├── regions/      {slug}.md (+ {slug}.state.md if control is contested)
│   ├── npcs/         {slug}.md + {slug}.state.md
│   ├── factions/     {slug}.md + {slug}.state.md
│   ├── locations/    {slug}.md + {slug}.state.md
│   └── items/        {slug}.md (+ {slug}.state.md if stateful)
├── arcs/             {slug}.md + {slug}.state.md
├── state/                           # GLOBAL / relational state, owned by no entity
│   ├── current.md                   # the "you are here" scene pointer (resume baseline)
│   ├── calendar.md                  # in-game date + event timeline
│   ├── threads.md                   # active leads/threads (a thread spans entities)
│   └── clocks.md                    # time-pressure dashboard (all clocks in one place)
├── characters/       {slug}.md + {slug}.state.md + {slug}.knowledge.md   # PC: sheet, state, ledger
├── sessions/         session-N-plan.md  session-N-transcript.md
│                     session-N.md (digest)  session-N-deltas.md
├── assessment/       session-N-assessment.md
├── documents/        verbatim handouts (letters, inscriptions, quoted text)
└── feedback/         per-skill player-feedback files
```

- **World-truth singletons** — `overview.md`, `cosmology.md`, `history.md` — are non-entity setting
  prose at fixed paths. They have **no slug, no `.state.md`, and no `INDEX` row** (like the `state/*`
  docs). `history.md` is the world's **backstory** — the past that produced the present — and is
  distinct from `state/calendar.md`, which is the *live* in-game clock (now and forward).
- **Regional history** is a **section inside each region file**, not its own entity.
- **Verbatim handouts** — the exact text of a letter, an inscription, an NPC's quoted line meant to
  be read aloud — go in `documents/`, not buried inside a digest or an entity file.

---

## 3. Stateful entities — the info / state pair

Every **stateful** entity (NPC, faction, active location, significant item, the PC) is **two files
that share a slug stem and sit side by side**:

- `{slug}.md` — **info / canon.** Who or what it *is*. Identity, personality, true allegiance,
  secrets, agenda. Update it when the underlying truth changes — a secret is revealed, an allegiance
  flips, who/what something is permanently shifts — via a gated edit.
- `{slug}.state.md` — **state.** Where it *is now*. Current disposition, location, condition, what
  it's doing. **Mutable** — rewritten at session boundaries by the dm's apply pass.

The **PC is a stateful entity like any other** and gets the full pair — `{slug}.md` (the sheet:
class, level, ability scores, features — update it on level-up, ability/feature change, or when a
new spell/ability first appears) + `{slug}.state.md` (current location, notable condition, key
items, objective) — **plus** one extra
PC-specific file: `{slug}.knowledge.md`, the epistemic ledger of what the PC knows, believes, and
wonders. The ledger sits *alongside* the state file; it does not replace it. **Don't track granular
mechanical resources** (HP, spell slots, coin) in state — the player owns those; record only
narratively significant state, exactly as for an NPC.

**State files are session-boundary snapshots, not a live feed.** A `.state.md` is accurate at
session *start* and is **frozen during play** — no agent rewrites it mid-session. During a session
the only live "now" is the transcript; the apply pass reconciles the snapshots afterward. So write
a `.state.md` as "true as of the start of session N," never as a running edit.

### Info file (`{slug}.md`) frontmatter + sections

```yaml
---
slug: lysa-fenn
name: Lysa Fenn
type: npc            # npc | faction | location | item | pc | region
status: active       # active | dormant | dead | destroyed | hidden | named-only
---
```

**The frontmatter above is universal; the body differs by type — use the matching template** in
`templates/` (`entity-npc`, `entity-faction`, `entity-location`, `entity-item`, `entity-region`).
They each follow the same arc: **surface** (what's openly apparent) → **deeper / hidden layer**
(the committed truth beneath) → **secrets** (flagged, §5) → **links** (§4). What changes per type is
the middle — an NPC has personality and an agenda; a faction has goals, structure, and reach; a
location has features and hooks; a region carries its own **regional history** section.

**World-truth docs are a separate, non-entity shape.** `overview.md`, `cosmology.md`, and
`history.md` are setting prose, not entities — no slug frontmatter, no state file, not in `INDEX`.
Use the `world-overview` / `world-cosmology` / `world-history` templates; they still carry the
surface/hidden two-layer structure.

### State file (`{slug}.state.md`) frontmatter + sections

```yaml
---
slug: lysa-fenn
layer: state
as-of: S5            # the session boundary this snapshot is true as of
---
```

Body: current **location**, **disposition** (toward PC / situation right now), **condition**
(health, status effects, resources), **what they're doing now / immediate intent**, and `[[links]]`
to any `clocks.md` clock they drive. Keep it short — state is the now, not the history.

---

## 4. Linking — `[[slug]]` wikilinks

Canon is **densely cross-linked**. Linking is not decoration; it is the anti-fabrication tripwire.

- **Every reference to a registered entity is a slug wikilink:** `[[lysa-fenn]]`,
  `[[old-watchtower]]`, `[[failing-light]]`. **Entity and arc links resolve through `INDEX.md`**
  (§6) — never by relative path, so files can move and only the registry path updates. **Thread and
  clock links** (`[[fenn-exposure]]`) are *not* in the registry — they resolve to their row inside
  `state/threads.md` / `state/clocks.md`, which are their home. The registry holds only file-backed
  things (entities and arcs).
- **A dangling link — an entity/arc `[[slug]]` that resolves nowhere (no registry row, and for
  clock/thread links no matching row in their dashboard) — is a fabrication tripwire.** It means
  one of two things: either the thing is real and must be **registered** (and, if load-bearing,
  fleshed out into a full file), or it was invented loosely and must be **grounded or removed**.
  The narrative-checker treats dangling links as findings; don't leave them.
- **You cannot write a duplicate without colliding on a slug** — which is the dedup guard. Before
  creating an entity, check `INDEX.md` for an existing slug or a role-overlapping entity. Reuse the
  existing one rather than spawning a second (the guard against two near-identical NPCs who should
  have been one).
- **Backlinks are derived, never hand-maintained** — to find what references an entity, grep
  `[[slug]]` across `campaign/`. Don't keep "referenced by" lists by hand.
- **Noise rule:** link *registered things* — entities, threads, clocks, arcs — at their **first
  mention per document**. Don't link every common noun, and don't re-link the same slug ten times
  in one file.

---

## 5. Awareness / hidden flags

Any secret, hidden motive, true nature, or planned reveal is **flagged** so the system tracks who
knows it — this is what lets NPCs act only on what they actually know, and what gates spoilers.

- Prefix the fact with **`[hidden]`** (the PC doesn't know it). It becomes **`[revealed: S<n>]`**
  the session the PC learns it.
- Add a **`Known to:`** line listing the in-world parties aware of it (NPCs, factions, and "the PC"
  once revealed).
- **Flag the secrets, not the surface.** Openly apparent details need no flag.

```
- [hidden] Lysa feeds the harbor patrol's rotation to the rebel cell.
  Known to: [[lysa-fenn]], rebel leadership.
```

The PC's `{slug}.knowledge.md` ledger is the mirror of these flags: it records what the PC has
actually learned, believes, and wonders. A reveal flips the flag here *and* there.

---

## 6. The registry — `INDEX.md`

One file, three jobs: **dedup guard** (owns the slug namespace), **slug→file resolver** (every
`[[link]]` resolves here), and **inventory** (every named entity at a glance). Every named entity
that has — or should have — a file is listed. Naming a thing in play or in a plan means it gets at
least a registry row, so it is never silently re-invented as someone else.

**What's registered:** the slug-addressed, file-backed things — the **PC**, NPCs, factions,
locations, items, **regions**, and arcs. **Not** registered: the world-truth singletons
(`overview/cosmology/history`) and the `state/*` docs (fixed paths), nor clocks/threads (they live
in their dashboards, §4).

Format: a table per entity type. Each row maps a slug to its files, status, and a one-line "who/what."

```markdown
# INDEX — Campaign Registry

## PC
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| bram-tully | Bram Tully | active | characters/bram-tully.md | characters/bram-tully.state.md | dockhand turned reluctant agent of the cell |

## NPCs
| slug | name | status | info | state | one-line |
|---|---|---|---|---|---|
| lysa-fenn | Lysa Fenn | active | world/npcs/lysa-fenn.md | world/npcs/lysa-fenn.state.md | harbormaster; secret rebel informant |
| the-cartographer | The Cartographer | named-only | — | — | mapmaker the PC was sent to find; file pending |

## Factions
| slug | name | status | info | state | one-line |
...

## Locations
...

## Regions
| slug | name | status | info | state | one-line |
...

## Items
...

## Arcs
| slug | name | status | design | state | one-line |
...
```

- **Slugs are kebab-case, derived from the canonical name** (`Lysa Fenn` → `lysa-fenn`). Stable:
  once assigned, a slug doesn't change even if a name does.
- **`status: named-only`** means the entity has been named but has no file yet. It still gets a
  row, so it can't be re-invented. **`named-only` is a *runtime-only* tolerance** — it exists so
  the runner can name a thing mid-session without stopping to author it. **It is never an
  acceptable resting state across a session boundary.** Both planning passes resolve it: the PRE
  pass fleshes out anything the upcoming plan will *use*, and the POST pass fleshes out anything
  that got named in play. Nothing should still read `named-only` once a PRE or POST pass has run —
  a lingering `named-only` is a dropped-entity bug.
- The narrative-checker checks *against* the registry; the planner bundle and the post-session
  deltas log *feed* it. The dm gates every addition.

---

## 7. Quick checklist before you finish writing

- [ ] Every load-bearing fact committed — no "DM decides / TBD / as needed" anywhere.
- [ ] Stateful entity? Both `{slug}.md` and `{slug}.state.md` exist, frontmatter filled.
- [ ] Every referenced entity is a `[[slug]]` link, first mention per doc.
- [ ] No dangling links — everything referenced is registered (or deliberately stubbed
      `named-only`).
- [ ] New entity checked against `INDEX.md` for slug/role overlap before creating.
- [ ] Secrets flagged `[hidden]` + `Known to:`; surface details left unflagged.
- [ ] `INDEX.md` row added/updated for anything created or renamed.
- [ ] Verbatim handout text routed to `documents/`, not inlined.
