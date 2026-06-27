# Campaign Engine Refactor — Design Doc

Status: **in design.** This is a living document. Tags: `[DECIDED]` = locked by the
owner, `[PROPOSED]` = my recommendation pending confirmation, `[OPEN]` = needs a
decision, `[TODO]` = agreed in principle, not yet specced.

The machinery being refactored lives in `.opencode/` (agents + skills + plugins). The
played campaign in `campaign/` is a **test campaign** — we may reset or roll it back
freely for testing; we are **not** hand-fixing its accumulated continuity. `[DECIDED]`

**Two separate git repos.** The **engine** (`.opencode/`, incl. this doc) is its own
repo; the **campaign** (root, incl. `campaign/`) is a different repo that *gitignores*
`.opencode/`. So: engine changes (agents, skills, plugins, REFACTOR.md) commit to the
`.opencode` repo; campaign artifacts (plans, world, state, sessions) commit to the
campaign repo. This doc lives at `.opencode/REFACTOR.md`.

---

## 1. Diagnosis

The system is three flows — **running**, **planning**, **note-taking/adjustment** —
where each layer trusts the layer below to hold continuity, and none actually does.

### Symptoms (session 5 was the clean demonstration)
- The runner placed the Foothills sealed room *inside the Athenaeum*; the player
  corrected the location twice in the first five exchanges.
- The runner fabricated a load-bearing NPC identity ("Eratha Voss") and an entire
  lineage on the fly, never checking canon, and admitted it when cornered:
  *"I invented 'Eratha Voss' and her entire backstory… because I didn't have a plan
  for what Corvin would tell you."*
- This contradicts the arc, which **already answers** who the lab intruder is:
  **Maren Voss, the Unbound operative** (`the-architecture-of-flesh.md`, Turning
  Point 2). Three layers (S4 runner, S5 planner, S5 runner) each spun up a *parallel,
  contradictory* identity for that NPC; nobody reconciled.

### Root causes, by flow
1. **Running.** The runner starts each session cold, reads ≈only the plan + ledger,
   and fabricates to fill gaps. It cannot audit itself (it never reliably did, which
   is why play is auto-captured rather than self-logged).
2. **Planning.** Plans are hand-wavey — they leave *world facts* the runner will need
   undetermined ("the woman's alias… not established in any campaign file — the DM
   creates as needed") while over-specifying beats. The planner reads the arc but does
   not **honor** it (it lists `the-architecture-of-flesh.md` as consulted, then invents
   the "Spiral Collective" and treats an already-cast NPC's identity as open).
3. **Note-taking / adjustment.** Capture is partial and the DM rubber-stamps delegated
   work. There is no canonical name/entity registry, so collisions multiply (see below).

### Adjustment audit (what each post-session commit actually changed)

| Artifact | S1 | S2 | S3 | S4 | Verdict |
|---|---|---|---|---|---|
| Knowledge ledger | +28 | +28 | +23 | +30 | **Working** |
| Assessment | full | full | full | full | **Working** |
| Feedback files | ✓ | ✓ | ✓ | ✓ | **Working** |
| Arc **body** | — | **+47 (real)** | 0 | 0 | **Flatlined after S2** |
| Arc status line | 1 ln | 1 ln | 1 ln | 1 ln | Recap only |
| World/NPC files | — | — | minor | created hadric/voss/shop | **Partial** |

- The post-S2 arc edit was a *genuine* adjustment (split Turning Point 2 into the
  5–6 "Foothills Return" and 7–9 "Sealed Room Opens"). Then arc adjustment **died** —
  S3 and S4 touched only the `## 7. Current Status` recap paragraph while play
  diverged hard from the arc body.
- World capture works for **met** entities but skips **named-but-not-yet-met** ones:
  **Corvin** was the centerpiece of the S5 plan yet has no file, so the planner had
  nothing to anchor to.
- **Name-collision catastrophe, unpoliced:** *Maren* (Athenaeum gatekeeper, in play) /
  *Maren Voss* (Unbound operative, `npc-maren.md`, never appeared) / *Sister Maren
  Voss* (Church, S4) — plus S5's invented *elder Maren Voss* and *Eratha Voss*. No
  registry exists to catch this; `npc-maren.md` got a band-aid "naming note" instead.

### What's working — do not break it
- **Initial worldbuilding** — solid, rich foundation.
- **Arc designer** — excellent structural work. *One fix:* it must **never say "DM
  decides"** (e.g. Thaddeus's fate). Punting decisions only works if the DM has teeth
  to resolve them, which it currently doesn't. The arc designer should commit.
- **Session assessments** — strong; whatever that prompt is doing, keep it.
- **Knowledge ledger updates** — consistent and substantive.

### Out of scope (known issues, not structural)
- Free model `opencode/mimo-v2.5-free` leaks foreign-language tokens into narration
  (e.g. `重新整理思绪` mid-sentence in S5). Model-choice issue.
- Runner occasionally skips rolls it should call (e.g. the S5 scry) — should be caught
  by the rules-checker below.

---

## 2. Cross-cutting principles `[DECIDED]`

- **Played beats planned.** What happened at the table is canon; the plan and arc are
  scaffolding. Divergence *from the arc* is allowed and propagates *upward* (the arc
  adjuster reconciles the arc to play). Contradiction *of what's already been played*
  is an error to block. The checkers and the arc adjuster must both encode this
  direction. The narrative-checker therefore **allows and logs** arc divergence rather
  than blocking it. `[DECIDED]`
- **The checkers are fully authoritative.** When a checker reports a violation, the
  runner must resolve it before the turn reaches the player.
- **Delegated output is a proposal, not canon.** Any agent the DM delegates to
  (the planner) produces drafts; the DM must actually review
  and edit them, not rubber-stamp. The DM needs teeth.
- **Subagents are pure workers.** They cannot delegate (no `task`) and **cannot touch
  the player.** Anything player-facing — character creation, any prompt or question to
  the human — must be a **primary** (`dm` or `dm-runner`). Subagents only read/write
  files and report back.
- **Least privilege.** Every agent declares a **minimal allowlist** of tools *and*
  skills — default-deny, not deny-a-few. No agent gets `webfetch`/`websearch` or skills
  it doesn't use.

---

## 3. Running flow — the per-turn check loop `[DECIDED in shape]`

The runner stops being the canon-holder. Its job per player message:

```
player message
   └─► runner drafts the turn
          └─► submit {drafted turn} to BOTH checkers in PARALLEL
              (checkers self-serve prior context from the running transcript —
               the runner relays only its draft, not the player's messages)
                 ├─ rules-checker   → list of rule violations (or PASS)
                 └─ narrative-checker→ list of canon/consistency violations (or PASS)
          └─► runner self-corrects against the union of both lists
   └─► corrected turn ──► player
```

- **Every turn.** `[DECIDED]` Self-auditing has failed repeatedly; the gate is
  unconditional.
- **Checkers return violations/instructions, not rewritten text.** `[DECIDED]` The
  runner self-corrects from a clear list. Because the output is a list (not edited
  prose), the two checkers run in **parallel** with no merge conflict — one round-trip
  of latency, not two. `[DECIDED]`
- **Single bounded pass.** One check → correct → send. A correction of the "defer /
  don't assert it" kind cannot reintroduce the same class of violation. `[DECIDED]`
- **Checkers self-serve their own context.** `[DECIDED]` The runner submits *only its
  draft*. Each checker retrieves what it needs — the player's recent messages and the
  scene-so-far from the running transcript (`session-{N}-transcript.md`), and for the
  narrative-checker, the relevant canon files. The runner is no longer responsible for
  forwarding player messages or guessing what context a checker wants.
- **Tooling / permissions.** `[DECIDED]` Permission pattern is **`'*': deny` then allow**
  the specific tools (default-deny via wildcard, not piecewise). Both checkers get
  **read retrieval**: `read`, `grep`, `glob`, `list`, `bash` (to `tail`/`grep` the
  transcript and pull files), `todowrite` (each role builds its step checklist first),
  and `skill` (to load its role skill). They do **not** touch canon: `edit`, `patch`,
  `task`, `webfetch`, `websearch` denied. **One carve-out (§6 fork → a):** the
  narrative-checker gets `write`, scoped by prompt to the single
  `session-{N}-deltas.md` log (not canon) — it writes its own deltas so the runner
  doesn't have to (keep the runner in creative flow). The rules-checker writes nothing.
- **Runner needs `task` permission.** Currently `task: deny` in `dm-runner.md`. It must
  be allowed to call the checkers. It still does not plan/assess/adjust — it stays in
  the chair, but is allowed to consult. `[DECIDED]`

### 3a. rules-checker `[DECIDED scope]`
Polices **conduct only — transcript-aware but canon-free.** It works from the drafted
turn, the recent transcript turns it pulls itself (the player's actual words, the
scene count for pacing), and its own **baked-in checklist** (not the `session-run`
skill verbatim — that skill is written for the *runner*, not for a checker; the
rules-checker gets a prompt written for *checking*). It reads no world/arc/ledger
canon. Checklist (all checkable from the turn + transcript):

- spoke or acted for the PC (words/decisions the player didn't supply)
- rolled on the player's behalf, or resolved an uncertain/risky PC action with no roll
- announced a DC
- missing a mandatory check (Persuasion to sway a swayable NPC; Deception whenever the
  PC lies)
- metagame leakage ("sessions," etc.)
- auto-narrated a transition/arrival/departure the player didn't choose
- double-volley (demanded the PC re-verbalize a conclusion already drawn)
- pacing (proposing to wrap after a single scene)

Because it needs no campaign knowledge, it is light and fast to warm. `[PROPOSED]`

### 3b. narrative-checker `[DECIDED scope]`
Holds canon (warm: loads at session start; refreshes via its own `bash`/`read` as
needed). Primary comparison is the **arc** and the **session plan**. **Explicit
instruction:** for any NPC, location, item, faction, or documented fact *named* in the
drafted turn, **find and read its file** (grep the registry/`world/`) and verify the
runner's details against it. It also pulls recent transcript turns for in-session
context. Its consistency baseline is **canon ∪ state-at-session-start ∪ this-session
transcript ∪ this-session deltas** (the new canon it has already logged this session),
with transcript + deltas superseding the (frozen) state snapshot for anything play has
moved past — see §5.3. Supplies the runner the *correct* information it's
trampling, not just a flag. It also owns **spoiler discipline** (moved here from the
rules-checker, because judging "did this reveal something the PC hasn't learned?"
requires the knowledge ledger). `[PROPOSED for the spoiler move]`

It enforces **consistency, not obedience to the plan.** It blocks only:
- **(a) contradiction of established/played canon** — ledger, prior session logs,
  world files; and
- **(b) ungrounded load-bearing fabrication** — a named, plot-weight entity or
  world-fact that is in neither canon nor the plan. Instruction to runner:
  *"ground it in canon/plan, or defer — don't invent identity on the fly."*

It must **not** drag the player back onto the plan/arc. A turn that follows the player
off-plan while staying consistent with established facts passes; the divergence is
logged for the arc adjuster, not "corrected." `[DECIDED]`

**Harmless color vs. load-bearing invention.** `[DECIDED]` *Every* newly named entity
is **logged** as "new canon asserted this turn" (cheap; feeds capture and the registry
directly); the checker only **blocks** when the entity contradicts canon, **overlaps or
duplicates an existing entity** (a second "Maren"), or is
load-bearing-and-should-have-been-planned. Ambient flavor (a market vendor) logs
through; an invented antagonist identity gets stopped. *Planning-side dependency:* the
"log" needs a destination (a per-session new-canon log that post-session capture and
the registry consume) — scaffolding to be added with the planning-side work.

### 3c. Dependency
The runner loop is small to spec but **inert until the planning/note-taking fixes
land**: the narrative-checker can only *verify* (vs. fabricate-flag) the runner's
Corvin lines if Corvin has a file with pre-established details, and "let divergence
stand and log it" only works if a live arc adjuster downstream consumes the log.

---

## 4. Planning flow — the PRE bundle `[DECIDED]`

### 4.0 The one rule
> **Commit every world-fact at authoring time; leave open only what the player decides.**

"Plan the facts not the path," "honor the arc," and "never say DM decides" are three
faces of this. The only legitimate openness is the *player's path*; punting a *fact*
downstream (to the runner, to "the DM decides later") is forbidden — that punt is
exactly what produced Eratha Voss. **Threshold:** applies to **load-bearing** facts
(identities, what an NPC knows/reveals, the answer behind a mystery, what a check
yields). Trivial ambient detail (a passing vendor's name) is the runner's to improvise
and gets logged at runtime — the *same* load-bearing line as the runtime harmless-color
rule (§3b). PRE and RUNTIME share one threshold.

### 4.1 The PRE pass — `dm`, inline (author → self-expand → verify)
1. **Situation report** — `campaign-analyst` (`campaign-assess`): tension, active
   threads, what needs attention.
2. **`dm` picks the arc beat(s)** to advance.
3. **`dm` writes the plan inline** (loads `session-plan`; §4.2), referencing entities by
   registry slug-link.
4. **`dm` self-expands**: authors/stubs any entity the plan needs that isn't yet in canon
   (grounded in arc/canon, full files, registered), so no plan reference dangles.
5. **`dm` verifies** by dispatching **`narrative-checker`** in its **`check-plan`** role —
   the *same engine* that gates runtime turns — and resolves every violation (§4.3).
6. **`dm` finalizes, commits** (`campaign: session N plan` — plans are *campaign-repo*
   artifacts, not `.opencode`), and **hands off spoiler-free**.

### 4.2 The plan's output contract (the `dm` authors it; `session-plan` skill)
- **Fact-resolution priority** for any identity/reveal/fact the session needs:
  (1) the **arc's** answer if it exists → (2) existing **canon/registry** → (3) else
  **decide it now and flag as new-canon-to-file.** Never blank, never punt.
- **No blanks.** Forbidden: "DM decides / as needed / the runner creates / TBD" for any
  load-bearing fact. The gate rejects them.
- **Honor the arc.** Never invent a parallel identity for an already-cast NPC. If the
  arc says the intruder is Maren Voss, the plan's "woman" *is* Maren Voss — not a new
  "Eratha."
- **Free license to create — thoroughly documented + dedup-checked.** When canon is
  silent (resolution step 3), the planner may freely introduce new NPCs/entities — it
  is *not* restricted to pre-existing canon. But every creation is **fleshed out
  thoroughly, like any other entity** (full info file — identity, personality, agenda,
  what they know, disposition, secrets, links — via the shared conventions skill, **not
  a stub**), registered, and **checked against existing entities for name/role overlap**
  before it's filed (§4.3). Inventing the world forward is fine; inventing a *redundant*,
  *colliding*, or *thinly-sketched* entity is not.
- **Fact vs. path.** Every reveal's *content* is fixed (the fact, its source NPC, the
  gate — auto or check-with-tiers, the ledger flag known/new/hidden). Every *player
  choice* stays open (situations + decision points, never scripted outcomes).
- **Structure unchanged.** Keep the existing section list (Opening State, Beats,
  Encounter Seeds, Discoveries, NPC Staging, Decision Points, Contingencies, Pacing) —
  the sections were fine; the missing thing was *discipline* (facts fixed, arc honored,
  no blanks), not different headings.

### 4.3 The `dm` PRE review-gate — teeth (twin of the POST runbook)
A checklist; mechanical items delegated to `narrative-checker`, judgment items owned by
the `dm`:
- `[NC]` every entity/fact slug-link resolves in the registry — no dangling/unfiled;
- `[NC]` every reveal flagged against the ledger (known/new/stays-hidden) — no beat
  assumes the PC knows what it doesn't;
- `[NC]` no identity/reveal contradicts the arc or invents a parallel for an
  already-cast NPC;
- `[NC]` every **newly created entity** is cross-referenced against existing entities —
  name/slug collision, role/function overlap (redundancy), contradiction — and flagged
  for the dm to **merge or differentiate** (the proactive four-Marens guard);
- `[dm]` every **newly created entity is thoroughly documented** (full info file, not a
  stub) and registered before the plan is finalized;
- `[dm]` no blanks / "DM decides" anywhere — every load-bearing fact present;
- `[dm]` the plan advances the intended arc beat;
- `[dm]` fact/path split honored (facts fixed, choices open);
- `[dm]` spoiler-free handoff prepared.

The same `narrative-checker` engine that gates runtime turns gates the plan — so the
**Eratha-Voss class of failure is caught a stage earlier, at planning, automatically.**

### 4.4 "Never say DM decides" — the `dm` (arc authoring)
The arc commits its answers at design time (Thaddeus's fate, the intruder's identity) —
those are what the planner *pulls*. Arc agents never defer a fact to "the DM decides";
that's §4.0 at the arc layer. The `dm`-gate rejects arcs or plans that punt.

---

## 5. Documentation model — the state substrate `[DESIGNED]`

### 5.0 Organizing axis: static truth vs. live state
Everything the system stores sorts into five buckets. The system is strong in four and
was nearly empty in the fifth — which is the root of most runner/planner failures.

| Bucket | Purpose | Owner | Cadence |
|---|---|---|---|
| **Canon / truth** | who/what things *are* (incl. hidden) | design agents + DM gate | rarely |
| **Narrative design** | the planned story + *the answers* | dm (arc authoring) | per session |
| **PC epistemic** | what the PC knows/believes/wonders | apply pass | per session |
| **History** | what happened (append-only) | capture + extractor | per session |
| **Current state ("the now")** | where everyone/everything *is now* | apply pass | per session |

"Current state" had **no home** before — agents reconstructed the now from the latest
digest + the arc status-line + drifting NPC `Current Situation` sections. That is why
the runner mislocated the sealed room and why "what's the in-game date" was
unanswerable. This section gives it a home.

### 5.1 Entities — the info / state sibling pair
Every **stateful** entity (NPC, faction, active location, item, companion, the PC) is
two files **stored side by side**, sharing a slug stem:

- `kael.md` — **info / canon:** identity, personality, secrets, true allegiance. Static.
- `kael.state.md` — **state:** current disposition, location, condition, what they're
  doing now. Mutable.

This generalizes the one artifact that already works best: `dallid.md` +
`dallid-knowledge.md`. The `.state.md` suffix (not a directory split) carries the
static/live distinction, so entity pairs keep **locality** while state stays
greppable (`**/*.state.md`). **Non-stateful** canon (cosmology, the Severing lore,
geography) has no state file. The arc gets a related but distinct treatment: `…-flesh.md`
(the **living design** — premise, turning points, committed answers; revised *between
sessions* by the dm, not edited during play) + `…-flesh.state.md` (a lightweight
progress snapshot: status, which turning points hit, position on the tension curve) —
which retires the overloaded status-line **without** freezing the design. The arc body
is not static: the keeper assesses and applies structural/detail changes to each arc
every session (§5.9); divergence is reconciled *into* the body, not parked in state.

### 5.2 Global / relational state — state owned by no entity
Some state belongs to a *relationship* or to the session, not to any one entity. It
gets a small set of central docs under `state/`:

- `current.md` — the "you are here" scene pointer (resume baseline).
- `calendar.md` — in-game date + event timeline (fixes the market-day problem).
- `threads.md` — active leads/threads (a thread spans entities; it is not a field on one).
- `clocks.md` — the time-pressure **dashboard**. Clocks *straddle*: a clock may be
  caused by an entity (Kael's scrutiny window) but is *read* as part of the whole board.
  Resolve denormalized-toward-the-dashboard: the authoritative clock lives in
  `clocks.md`; the entity's `.state.md` just links to it. One read to see all pressure.

### 5.3 State timing — snapshots, not live `[DECIDED]`
State files are **session-boundary snapshots**: accurate at session start (the apply
pass wrote them), **frozen during play**. No mid-session state writer — the only live
"now" mid-session is the transcript. The runner cold-starts from `current.md` (+
links); from there the transcript carries the now until the next apply pass reconciles.
Consistency baseline for the narrative-checker: **canon ∪ state-at-session-start ∪
this-session transcript**, transcript superseding the snapshot for anything play has
moved past. (No new agent — consistent with the auto-capture philosophy.)

### 5.4 Registry / resolver — `INDEX.md` `[DESIGNED]`
One artifact, three jobs: (1) **dedup guard** — owns the slug namespace, so you cannot
silently spawn a second "Maren"; (2) **slug→file resolver** for all links, which
de-risks the restructure (move files, update one path); (3) **inventory** — every
named entity → {info file, state file, status, one-line who}. The narrative-checker
checks *against* it; the planner bundle and the reconciliation log *feed* it.

### 5.5 Reconciliation log — `sessions/session-{N}-deltas.md` `[DESIGNED]`
Destination for the narrative-checker's in-play findings; two entry types —
**new-canon asserted** (drained post-session by the dm into world files + registry) and **arc
divergence** (drained by the arc adjuster). **Capture finding:** the existing
`dm-transcript.ts` plugin records only player↔runner *text* from the runner's own
session; checkers are separate subagent sessions, invisible to it — their findings must
be persisted deliberately. *Write-mechanism fork — §6.*

### 5.6 Linking — slugs, resolved through the registry `[DECIDED]`
- **Slug wikilinks** (`[[kael]]`), registry-resolved — not relative paths (which break
  on every move).
- **Dangling link = the anti-fabrication tripwire.** Every named-entity reference is a
  link; an unresolved link is either *register it* (harmless color) or *block it*
  (ungrounded load-bearing). Turns the checker's fuzziest judgment into a cheap check.
  You also can't write a duplicate without picking a slug — dedup falls out for free.
- **Backlinks are derived, never hand-kept** — grep `[[slug]]` on demand ("what
  references Kael?"); this is what the arc adjuster uses to find what goes stale.
- **Noise rule:** link *registered things* (entities, threads, clocks, arc beats),
  first mention per doc — not every common noun.

### 5.7 Proposed layout `[PROPOSED]`
Static/live carried by suffix + registry, **not** a top-level canon/state split (that
would break entity-pair locality).
```
campaign/
├── INDEX.md                      # registry / slug resolver
├── world/
│   ├── overview.md  cosmology.md  history.md   # world-truth singletons (not in INDEX, no state)
│   ├── regions/        coastlands.md (+ .state.md if control contested)   # slug entity; holds regional history
│   ├── npcs/        kael.md + kael.state.md            (siblings)
│   ├── factions/    wardens.md + wardens.state.md
│   ├── locations/   foothills-lab.md + foothills-lab.state.md
│   └── items/       orrery.md (+ .state.md if stateful)
├── arcs/            architecture-of-flesh.md + .state.md
├── state/                        # GLOBAL/relational state only (no entity owner)
│   ├── current.md  calendar.md  threads.md  clocks.md
├── characters/      dallid.md + dallid.state.md + dallid.knowledge.md  (sheet · state · ledger)
├── sessions/        session-N-{plan,,transcript,deltas}.md   (history)
├── assessment/      session-N-assessment.md
├── documents/       verbatim handouts  (fix routing — see 5.8)
└── feedback/
```

### 5.8 Routing fixes
- **`documents/` is unused** — verbatim handouts (Hadric's description, Kael's quotes)
  landed in the digest. The capture/apply flow must route verbatim material here.
- **Named-but-not-met entities need a home on first mention** (the Corvin gap): the
  moment an entity is *named* it gets at least a registry entry, so it's never silently
  re-invented as someone else. Any entity a plan will actually *use* is **fleshed out
  thoroughly** (full info file), not left as a stub — see §4.2.

### 5.9 Adjustment (note-taking) flow consequence
**The arc adjuster must adjust the arc body**, not just a status recap — it consumes
the reconciliation log's divergence entries + the digest and reconciles the arc
`.state.md` (and, when play overtakes design, the arc body) to what was played.

### 5.10 Ownership × timing `[DESIGNED]`

**Phases:** `INIT` (setup, once) · `PRE` (planning, before a session) · `PLAY` (live) ·
`POST` (reconcile/adjust, after a session).
**Agents:** `dm` (orchestrator; authors all canon, plans + state inline) · `runner` · delegated:
`CA` campaign-analyst, `LE` log-extractor · RUNTIME: `NC` narrative-checker, `RC` rules-checker ·
*plugins* (deterministic). `SP` below = the **dm's PRE planning pass** (inline; formerly a separate
session-planner agent — culled). World/arc/plan authoring is all the `dm`'s. See §7.

**Four governing rules:**
1. **Single writer per artifact per phase.** Shared ownership is what produced the
   drift; every file has exactly one writer in any given phase.
2. **Snapshot vs. record.** *Snapshots* (`*.state.md`, `state/*`) are **frozen during
   PLAY** and rewritten only at POST. *Records* (transcript, deltas) are append-only
   and accrue during PLAY. No agent maintains a *current view* mid-session.
3. **Only two things write during PLAY:** the transcript (plugin) and the deltas log
   (NC or plugin — §6 fork). Everything else is PRE or POST.
4. **Delegated writes are proposals; the `dm` gate makes them canon.** This is where
   "DM with teeth" lives — the gate is an actual cross-ref against registry + arc, not
   a rubber stamp.

**Canon / truth**
| Artifact | Writer · phase | Gate | Read by |
|---|---|---|---|
| `INDEX.md` (registry/resolver) | dm·INIT (bulk); dm·PRE (staged-new + named-but-not-met stubs); dm·POST (entities asserted in play, from deltas) | dm | runner, NC, SP |
| `world/{overview,cosmology,history}` (world-truth singletons) | dm·INIT; dm·POST if play establishes new world-truth | dm | SP, NC |
| `world/{npcs,factions,locations,items,regions}/{slug}.md` (info) | dm·INIT; dm·PRE/POST for first-introduction | dm | runner, SP, NC |
| `arcs/{arc}.md` (design) | dm·INIT; dm·POST when play overtakes design | dm | SP, NC, dm |

**PC epistemic**
| `characters/{pc}.md` (sheet) | dm·INIT; POST on level-up/permanent change | dm | runner, SP, NC |
| `characters/{pc}.knowledge.md` (ledger) | apply pass (dm)·POST, from digest | dm owns | runner, SP, NC |

**Current state — snapshots, frozen during PLAY**
| `world/**/{slug}.state.md` | apply pass·POST (digest+deltas) | dm | runner (session start), SP, NC |
| `characters/{pc}.state.md` (PC location/notable condition/key items/objective; no granular HP/slots) | apply pass·POST (digest+deltas) | dm | runner (session start), SP, NC |
| `arcs/{arc}.state.md` | dm·POST (apply pass; body re-design is also the dm's) | dm | SP, dm |
| `state/{current,calendar,threads,clocks}.md` | apply pass·POST | dm | runner (session start), SP, NC |

**History — append-only**
| `sessions/session-N-plan.md` | dm·PRE (planning pass + self-gate via check-plan) | dm | runner, NC, CA |
| `sessions/session-N-transcript.md` | transcript plugin·PLAY (auto) | — | LE, CA, NC (in-session) |
| `sessions/session-N.md` (digest) | LE·POST (from transcript) | dm | CA, dm (apply) |
| `sessions/session-N-deltas.md` (reconciliation log) | NC·PLAY (narrow write, scoped to this file) | — | dm apply pass·POST |
| `assessment/session-N-assessment.md` | CA·POST (from digest) | — | dm, SP (next PRE) |
| `documents/*` (verbatim handouts) | LE/apply pass·POST (routed from transcript) | dm | runner, SP, NC |

**Process**
| `feedback/*.md` | dm·POST (from digest's player-feedback section) | — | the targeted skill/agent, at its phase |

**The canon/state ownership seam `[DECIDED, revised post-M1]`:**

> The `dm` **authors all canon, plans, and state**, as the single auditor. No delegated agent
> writes a real campaign file (analysts/extractor produce their own non-canon deliverables; the
> narrative-checker writes only the deltas log).

- **The apply pass is the `dm`** (not a delegate). It owns and performs all POST writes —
  new/changed canon (world, arcs, entities), every changed `*.state.md`, the four `state/*`
  docs, the ledger, the registry, document routing. One mind auditing the whole pass is
  what smooths inconsistencies, and the same mind authored the canon, so there's no
  hand-off to drop.
- **§5.10 is the `dm`'s POST runbook.** Teeth come from the matrix-as-checklist: a
  closed list where every changed entity and every delta entry must be accounted for.
  Mitigates the heavy-single-pass risk (the way Corvin got dropped) by keeping it
  *transcription from structured digest+deltas, not re-analysis*.
- **Why inline, not delegated authoring:** same model everywhere (no quality gain from a
  worker), and the author/gate split only enabled rubber-stamping. The independent check
  is the `narrative-checker`, not a separate author. The craft lives in skills the `dm`
  loads (`world-build`, `arc-design`, `canon-conventions`).

---

## 6. Open decisions

**Runner side: fully resolved.** All decisions folded into §2–§3 — parallel execution,
single bounded pass, spoiler discipline → narrative-checker, checkers self-serve
context with read-only `bash`, played-beats-planned (allow + log arc divergence), and
the harmless-color threshold (log every new entity, block only contradictory/
load-bearing). The one carried dependency is the new-canon **log destination**, which
ships with the planning-side work (§4–§5).

**How checker findings reach the reconciliation log — RESOLVED → (a).** The
narrative-checker **writes `session-{N}-deltas.md` itself** (a `write` carve-out scoped
by prompt to that one non-canon file). Chosen over the plugin route to **keep the runner's
load minimal** — the runner should stay in creative flow and never handle bookkeeping; the
checker is already reading everything it needs to produce the deltas, so it logs them and
returns only the violation list. The checker also reads the deltas it has already written
this session, so its own logged canon is part of its consistency baseline (§3b).
*(Rejected (b) plugin-capture: more plumbing, and the checker is the natural writer here.)*

**Documentation model: designed** (§5) — info/state sibling pairs (`.state.md`
suffix), global state docs, snapshot timing, registry/slug resolver, slug wikilinks +
derived backlinks + noise rule. `[DECIDED]` Layout (§5.7) `[DECIDED]` — **rebuild, not
migrate** (both campaign content and prompts); INIT must scaffold the entire §5.7
layout from an **empty directory**.

**Ownership × timing matrix: designed** (§5.10). `[DECIDED]`

**Ownership seam: decided** (§5.10, revised post-M1) — the `dm` authors all canon + writes
all state (single auditor; matrix is its runbook). **No delegated agent writes a real campaign
file.** **Builder/keeper/planner agents culled** in favor of `dm`-inline authoring.

**Resolved this round:** Migrate-vs-rebuild = **rebuild**. Character creation = **stays a
`dm` skill** (subagents can't touch the player). World/arc authoring = **`dm`-inline via
craft skills**, not builder/keeper agents (post-M1).

Still open:
- **Planning flow (§4): designed `[DECIDED]`** — the one rule (commit facts / leave path
  open), the dm's inline PRE planning pass, the plan output contract, the dm PRE
  review-gate (reusing `narrative-checker` `check-plan`), "never say DM decides." Confirmed:
  load-bearing no-blanks threshold, existing plan section structure kept, NC/dm gate
  split. **Added:** planner has free license to create entities, but each must be
  **thoroughly documented** (full file, not a stub) and **overlap-checked** (name + role)
  against existing entities — so the planner authors its own new-entity files via the
  conventions skill (the `dm` handles deeper/POST authoring inline).
- **Build-time check:** does opencode support a *per-skill* allowlist, or only blanket
  `skill: allow/deny`? (Affects how §2 least-privilege is enforced for skills.)

## 7. Agent inventory — lifecycle taxonomy

> **Post-M1 revision (2026-06-26).** Running INIT showed the `dm` authoring world/arc canon
> *inline* rather than delegating, and it worked. Decision: **cull the builder/keeper agents; the
> `dm` authors all canon inline** via the craft skills. Two premises corrected: (1) **every** agent
> (dm, runner, subagents) runs the **same** model (`mimo-v2.5-free`) — there's no quality gain from
> delegating authoring; (2) the engine **targets a modest, non-frontier model** — reliability must
> come from *prompt structure*, not model smarts. Hence the `narrative-checker` must be **strictly
> algorithmic**, likely **decomposed into focused checking skills**.

**Architectural constraint (verified):** every subagent has `task: deny` — only the
`dm` and `dm-runner` (primaries) can spawn agents. **Subagents cannot delegate.** All
multi-agent orchestration is the conductors'.

**Organizing principle: split by disposition (lifecycle), unify by format.** An INIT
prompt ("create from a brief") and a maintenance prompt ("surgical change against a
large corpus, never retcon") are *opposite* dispositions — cramming both into one
agent muddles the prompt (plausibly why arc Mode B degraded to status-line recaps). So
agents split per lifecycle, **but** all canon-writing agents load **one shared
canon-conventions skill** (registry, slug-links, info/state suffix, file layout) so
they don't drift in *how* they write. Disposition → agent prompt; format → shared skill.

**Conductors (primary):**
- `dm` — orchestrates INIT and BETWEEN-SESSIONS; **authors all canon inline** (world, arcs,
  entities) via `world-build` / `arc-design` / `canon-conventions`; owns the apply pass + all
  gates + all state. Must *actually revise arc bodies* on divergence, not do status-line recaps.
- `dm-runner` — orchestrates RUNTIME; `task: deny` → allow (calls checkers); adopts the
  per-turn check loop (§3).

**Canon, plans, and state are the `dm`'s, inline** (no builder/keeper/planner agents). The dm writes
world/arc/entity files **and session plans** directly at INIT, PRE, *and* POST — with
`narrative-checker` as the independent gate (`check-plan` at PRE, `check-turn` at runtime,
`check-propagation` at POST). The craft lives in **skills** the dm loads (`world-build`,
`arc-design`, `session-plan`), unified by the **`canon-conventions`** format skill. Disposition (init vs. surgical
maintenance) is handled by the dm's phase instructions, not by separate agents. `character-create`
stays a dm-driven skill (player-facing). Trade-off: INIT context load sits on the dm — acceptable;
reintroduce a builder agent only if it bloats.

**Delegated subagents** (isolation / parallelism only):
- `campaign-analyst` — assess (PRE) + review (POST); analysis only, writes its own deliverable. Keep.
- `log-extractor` — transcript → digest, lossless, POST. Keep.
- `narrative-checker` — canon/consistency gate (§3b); **reused by the `dm` PRE review**; **strictly
  algorithmic, decomposed into focused checking skills** (the many-jobs problem).
- `rules-checker` — conduct gate, canon-free (§3a); strictly algorithmic.

**State application is the `dm` directly** (§5.10).

**Net change:** the `canon-conventions` skill + two runtime checkers (`narrative-checker`,
`rules-checker`). World/arc/**plan** authoring folds **into the `dm`** (inline, via the existing
craft skills) — no builder, keeper, or planner agents. *(Earlier drafts planned `world-builder`/
`arc-builder`/`world-keeper`/`arc-keeper`/`session-planner`; all culled in favor of dm-inline
authoring with the `narrative-checker` as the independent gate.)*

---

## 8. Build order `[PROPOSED]`

Principle: **substrate → producers → consumers**, sequenced along the lifecycle
(create → plan → play → reconcile). Each phase produces what the next consumes, so each
ends at a **review milestone** with real output. Each numbered chunk is **one reviewable
diff**; we don't advance until it's reviewed. All chunks are `.opencode` (engine) repo
unless noted; generated campaign instances land in the campaign repo. Least-privilege
allowlists are applied **per chunk** as each agent is (re)written, with a final audit.

Dependencies: `0 → 1 → 2 → {3, 4} → 5 → 6`.

### Phase 0 — Foundations *(pure docs/templates; no behavior)*
- **0.1 Canon-conventions skill** — the shared house style every writer loads: entity
  info/state split + frontmatter, slug rules, `[[slug]]` linking (+ dangling =
  fabrication), registry format, §5.7 layout, the "commit facts / never say DM decides"
  authoring rule.
- **0.2 Templates + a worked example** — templates for entity-info, entity-state, the
  four `state/*` docs, `INDEX`, and the deltas log; **plus one hand-authored example
  entity pair + sample registry** to validate the format reads well before agents mass-
  produce in it.
- ▶ **Review:** does the format actually read cleanly and capture what each flow needs?

### Phase 1 — INIT producers → a fresh campaign ✓ DONE
- **1.1 `world-build` skill** — world-authoring craft in the new layout; format → conventions.
  *(The `world-builder` agent was built then culled post-M1; the `dm` authors world inline.)*
- **1.2 `arc-design` skill + arc templates** — design craft; **commit every answer**; arc design is
  a living doc. *(The `arc-builder` agent was built then culled post-M1; the `dm` authors arcs inline.)*
- **1.3 `character-create` skill** — PC triple (sheet/state/knowledge) in the new format
  (dm-driven; player-facing).
- **1.4 `dm` INIT orchestration** (campaign-setup) — scaffold §5.7 from an **empty dir**,
  init `INDEX` + empty `state/*`, `dm` authors world/character/arc inline and gates each, `dm`
  initializes all state.
- ▶ **Milestone M1: PASSED** — INIT ran from empty; output reviewed at a skim. Findings folded back:
  builders/keepers culled, Stage 1/2 over-asking tightened.

### Phase 2 — The gate ✓ DONE *(reused by planning AND runtime)*
- **2.1 `narrative-checker`** — thin role-loader; roles `check-turn`/`check-plan`/`check-propagation`
  (decomposed by role). Writes only the scoped deltas log.
- **2.2 `rules-checker`** — conduct gate, canon-free, checklist in-prompt.
- All task-list-first; deny-`*` swept across every agent. *(Standalone seeded-draft test is
  user-runnable; deferred to in-flow testing at M2/M3.)*

### Phase 3 — Planning → a reviewed plan
- **3.1 `session-plan` skill overhaul** — the §4 contract (facts/path, honor arc, free-license +
  thorough docs + overlap, slug-links, no blanks); the `dm` loads it (no planner agent).
- **3.2 `dm` PRE pass + check-plan gate** — dm authors the plan inline (author → self-expand →
  verify with `narrative-checker` `check-plan`); this also completes INIT's session-1 plan.
- ▶ **Milestone M2:** generate session-1 plan as a bundle; review it, and watch the gate
  catch a seeded problem (a blank, an arc contradiction, a duplicate entity).

### Phase 4 — Runtime → play a session
- **4.1 `dm-runner`** rewrite — the per-turn parallel check loop; `task: allow`; reads
  `state/current` + ledger + plan.
- **4.2 Deltas-log capture** — resolve the §6 a/b fork (plugin capture vs. NC narrow-
  write) and build it.
- ▶ **Milestone M3:** play a short session against M2; verify the loop, both checkers
  firing, and deltas accruing.

### Phase 5 — POST reconcile → updated canon/state
- **5.1 `log-extractor`** — keep; minor (digest references deltas).
- **5.2 `campaign-analyst`** — keep; minor (reads new layout).
- **5.3 `dm` POST apply-pass runbook** — the §5.10 checklist, all done by the `dm` inline: drain the
  deltas (author new-canon entity/world files + registry; reconcile arc bodies — *not* a status
  bump), write all state files + ledger, route documents; gate throughout. *(POST canon authoring
  folds into the `dm`; no `world-keeper`/`arc-keeper` agents — post-M1.)*
- ▶ **Milestone M4:** reconcile M3; review updated state/ledger/registry/arc — verify
  nothing dropped (the Corvin test) and the arc body actually moved.

### Phase 6 — Cross-cutting + integration
- **6.1 Least-privilege audit** across all agents (tool + skill allowlists); resolve the
  per-skill-allowlist capability question.
- **6.2 Model choice** (if in scope) — checker reliability vs. `mimo-v2.5-free`.
- ▶ **Milestone M5:** full loop — INIT → plan → play → reconcile → plan next —
  end-to-end coherence test.
