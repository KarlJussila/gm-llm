---
name: canon-conventions
description: The shared house style for writing campaign canon — file layout, entity info/state file pairs and frontmatter, slug naming, [[slug]] linking, the INDEX registry, awareness/hidden flags, and the "commit every fact, never say DM decides" authoring rule. Load this whenever you author or edit any file under campaign/ so every writer stays consistent in *how* canon is recorded.
---

# canon-conventions

This is the **format contract** every canon-writing agent shares. It governs *how* the campaign is
recorded — file layout, naming, linking, frontmatter — so that the world-builder, arc-builder,
session-planner, world-keeper, arc-keeper, and the dm's apply pass all write the same shape of file
and never drift. *What* to write is each agent's own job; *how* to write it is here.

Read this before authoring or editing anything under `campaign/`. When this skill and an agent's
own prompt both speak to format, this skill wins.

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
│   ├── cosmology.md  overview.md    # non-stateful world truth (no .state.md)
│   ├── regions/      {slug}.md
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

- **Non-stateful canon** (cosmology, the deep lore, fixed geography) gets **no** `.state.md`.
- **Verbatim handouts** — the exact text of a letter, an inscription, an NPC's quoted line meant to
  be read aloud — go in `documents/`, not buried inside a digest or an entity file.

---

## 3. Stateful entities — the info / state pair

Every **stateful** entity (NPC, faction, active location, significant item, the PC) is **two files
that share a slug stem and sit side by side**:

- `{slug}.md` — **info / canon.** Who or what it *is*. Identity, personality, true allegiance,
  secrets, agenda. **Static** — changes only when the underlying truth changes (rare), via a gated
  edit.
- `{slug}.state.md` — **state.** Where it *is now*. Current disposition, location, condition, what
  it's doing. **Mutable** — rewritten at session boundaries by the dm's apply pass.

The **PC is a stateful entity like any other** and gets the full pair — `{slug}.md` (the sheet:
class, abilities, fixed traits) + `{slug}.state.md` (current location, HP, conditions, resources,
what's in hand) — **plus** one extra PC-specific file: `{slug}.knowledge.md`, the epistemic ledger
of what the PC knows, believes, and wonders. The ledger sits *alongside* the state file; it does
not replace it. Knowledge is not the PC's only mutable dimension — location and condition change
too, and live in `.state.md` exactly as they do for an NPC.

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

Body sections (adapt to type; omit what doesn't apply):
- **Identity / Public role** — what's openly apparent.
- **Personality / mannerisms** (NPC) or **Goals & methods** (faction) or **Description &
  significance** (location/item).
- **Deeper layer / true nature** — the real story, including hidden allegiances.
- **Agenda / what they want.**
- **What they know** — facts this entity is aware of (gates how they can act).
- **Disposition toward the PC.**
- **Secrets** — flagged per §5.
- **Links** — `[[slug]]` references to related entities, arcs, threads (see §4).

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
  `[[old-watchtower]]`, `[[failing-light]]`. Links resolve through `INDEX.md` (§6), never by
  relative path — so files can move and only the registry path updates.
- **A dangling link — a `[[slug]]` with no registry entry — is a fabrication tripwire.** It means
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

Format: a table per entity type. Each row maps a slug to its files, status, and a one-line "who/what."

```markdown
# INDEX — Campaign Registry

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
