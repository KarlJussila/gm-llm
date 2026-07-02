# D&D Campaign Management System for opencode

## Purpose

A set of opencode skills and agents that enable an LLM to design, run, and maintain documentation for a tabletop D&D campaign. The system handles macro-scale narrative planning, session-to-session assessment, session preparation, live session assistance, and post-session review — with an orchestrator that coordinates these tasks without overloading any single model context.

## Features

### Campaign Lifecycle Management
- Initialize a new campaign through a guided, staged setup flow (see below)
- Maintain campaign state across sessions (world, characters, narrative arcs)
- Track the campaign timeline (in-game and real-world)
- Conclude a campaign with a wrap-up assessment

### Guided Campaign Setup
- Start from the player's target vibe — as vague or specific as they offer
- Optional standard questionnaire to narrow setting, tone, themes, stakes, play-style, and
  content boundaries (lines & veils)
- A control dial spanning player-led, collaborative, and DM-led ("surprise me") flows
- Design the world skeleton first, then present a spoiler-free premise plus a few character hooks
- Collaboratively create the character: concept, world placement, and backstory (mechanical
  details recorded as the player provides them)
- Weave at least one major arc into the character's backstory before the first session — kept
  spoiler-free to the player

### Macro-Scale Narrative Planning
- Design multi-session narrative arcs with premise, turning points, and tension curves
- Plan multiple possible player engagement paths for each arc
- Track arc status (dormant, building, climax, resolved)
- Identify hooks that draw players into arcs

### Session-to-Session Assessment
- Analyze player engagement patterns across sessions (what they leaned into, what they skipped)
- Evaluate narrative health (are arcs advancing, stalling, or need adjustment)
- Identify unintended consequences of player actions
- Flag unresolved threads and new hooks that emerged

### Narrative Arc Adjustment
- Revise arc trajectories based on player actions
- Accelerate, decelerate, or redirect arcs based on engagement
- Update tension curves and turning points
- Maintain story coherence while adapting to player choices

### Session Planning
- Prepare for a specific upcoming session based on current campaign state
- Identify likely player actions and plan contingencies
- Design encounter seeds and decision points
- Create flexible session structure that can adapt mid-session
- Avoid over-planning while ensuring narrative threads are advanced

### Session Execution Assistance
- Improvise around player choices during live play
- Track state changes in real-time (world, characters, factions)
- Suggest narrative beats that advance active arcs
- Maintain campaign tone and themes during improvised content
- Resolve improvised situations while respecting established lore

### Post-Session Review
- Compare planned session events vs. actual events
- Identify what worked and what didn't
- Produce actionable insights for arc adjustment and future planning
- Update character states, world state, and faction positions
- Note-taking is automatic: the play transcript is captured by a plugin during the session, then
  the `dm` delegates to `log-extractor` to produce a structured digest (`session-{N}.md`) and
  applies it to canonical state — knowledge, world, items, documents — post-session

### Player Feedback Loop
- Collect player feedback at session end (runner asks; recorded verbatim in the session log)
- Distill feedback into per-skill / per-agent guidance files under `campaign/feedback/`
- Each skill and primary agent loads its own feedback file as binding guidance, so the system
  adapts to the player over time without editing the framework (`.opencode/`)

### Campaign Documentation
- Maintain human-readable markdown files for all campaign state, one home per kind of
  information (see `campaign/README.md` for the layout and capture conventions)
- Capture verbatim the text of in-world written materials (letters, journals, inscriptions) in
  `campaign/documents/` at the moment they are shown to the player
- Track significant objects/artifacts (owner, location, state, history) in `campaign/world/items.md`,
  separate from mundane gear on character sheets
- Record improvised canon to its world file the moment it is created during live play
- Support diffing and version control of campaign changes
- Keep session logs, character sheets, and world lore organized

### Knowledge & Awareness Tracking
- Track what the player character knows separately from what the DM knows, so the boundary is a
  data structure rather than a behavioral guideline
- A live PC knowledge ledger (`characters/{name}-knowledge.md`) — Knows / Believes (incl.
  misinformation) / Open questions — read at session start and updated as the character learns
- Awareness flags on stored facts (`[hidden]` / `[revealed: S<n>]`) with a `Known to:` list of the
  in-world parties aware of each secret — so NPCs act only on what they know and information can
  spread
- Session plans flag each clue/reveal as known, a new reveal, or staying hidden, sourced from the
  ledger

## Architecture

Two primary agents the player starts directly, a set of subagents they delegate to, and a set of
skills that hold the actual procedures (one home each — the single source of truth).

**Primary agents:**
- **`dm`** — the between-sessions brain. Initializes the campaign, assesses state, plans the next
  session, reviews finished ones, and adjusts arcs and world state. Delegates production work to
  subagents and commits to git. It does **not** run live sessions.
- **`dm-runner`** — runs one live session (narration, NPCs, improvisation, dice), then stops. It
  does **not** take notes, plan, assess, or adjust arcs (the transcript is auto-captured).

**Subagents** (`mode: subagent`, delegated via the native `task` tool, never started by the player):
the `dm`'s production delegates — a read-only `campaign-analyst`, `log-extractor` (transcript →
digest), and `character-importer` (a character file → the PC sheet) — plus the runtime gate agent
`narrative-checker`. It is a thin wrapper that loads one of its role skills (`check-turn` +
`check-conduct` at runtime, `check-plan`/`check-digest`/`check-propagation`/`check-feedback`/
`check-init` between sessions), does the task, and returns a Result / Evidence / Changes / Caveats
report. At runtime the canon and conduct checks run in one warm session — conduct benefits from
the canon/ledger context the canon check just loaded.

**Skills** (procedures, reused by both agents and subagents): `campaign-setup`, `campaign-intake`,
`character-create`, `character-import`, `world-build`, `arc-design`, `session-plan`, `session-run`, `session-flow`,
`social-play`, `discoveries`, `campaign-assess`, `session-review`, `log-extract`, plus the focused
session-level skills below.

**Session-level skills come in a few groups, by a flat naming convention** (opencode discovers skills
from `.opencode/skills/<name>/SKILL.md`, so the type lives in the name, not in subdirectories).
Many table concerns — investigation, NPCs, encounters/combat, pacing — have both a *planning* face
and a *running* face, and the content differs between them:

- **`*-plan` skills** — pulled by `session-plan` (the planning orchestrator) when designing a
  session: `encounter-plan`, `investigation-plan`, `npc-plan`, `pacing-plan`. Planning is
  deliberate and sectioned, so these are loaded as needed.
- **Runner craft skills** — the live craft `dm-runner` loads each session. `session-run` is the
  always-on core (agency, rolls, spoilers, applied every turn); it loads companions as the scene
  calls for them — `session-flow` (open / pace / close, including end-of-session feedback),
  `social-play` (conversations and playing NPCs), and `discoveries` (revealing information). The
  runner's algorithm opens by loading these, then plays.
- **`*-run` skills** — reserved for a distinct *play mode* `dm-runner` enters (e.g. a forthcoming
  `combat-run`), as opposed to the always-resident craft skills above.

The campaign-lifecycle skills (`world-build`, `arc-design`, `campaign-setup`, `campaign-intake`,
`campaign-assess`, `session-review`, `log-extract`, `character-create`) are neither — they are the
`dm`'s between-session authoring and management procedures.

**Boundaries that prevent role bleed:**
- The two roles are separate primary agents; the player starts whichever phase they're in.
- `dm` is explicitly barred from running sessions; `dm-runner` is explicitly barred from
  planning, assessing, and arc work.
- Post-session work belongs to `dm`: the runner just plays (the transcript is auto-captured), and
  `dm` extracts the log and reviews it fresh between sessions.
- **Spoiler discipline:** the human is the player and has not read the planning files. Both
  primary agents keep spoiler-bearing content (upcoming beats, twists, NPC secrets) in files and
  out of conversation, narrating only what the character can perceive.

## External Integrations

- **Dice rolling:** the `dice` tool (opencode plugin at `.opencode/plugins/dice-roller.ts`) for
  random resolution during play.
- **Per-turn craft reminder:** the orchestrator (`orchestrator/loop.py`) prepends the runner's
  per-turn DM *craft* loop (agency, ask-for-a-roll, narrate-the-response) to each player message, so
  the craft stays salient and resists decay over a long session.
- **Automatic transcript capture:** the orchestrator writes
  `campaign/sessions/session-{N}-transcript.md` from each turn's final messages (player + corrected
  DM narration). Note-taking never depends on the model.
- **Delegation:** the native `task` tool targeting `mode: subagent` agents — no subprocess
  spawning (`opencode run`).
- **Markdown files:** all state is stored in human-readable markdown (no database).
- **Git:** campaign state changes are committed to the **campaign repository** to hand off between
  the `dm` and `dm-runner` phases (see Repository Layout).

## Repository Layout

The framework and the campaigns it generates are tracked in **separate git repositories**, so
framework development and play history don't entangle:

- **Framework repo — rooted at `.opencode/`.** Tracks the agents, skills, plugins, and this spec.
  It is self-contained and portable: drop `.opencode/` into any opencode project to use the
  framework. `node_modules/` is the only ignored content.
- **Campaign repo — rooted at the project root.** Tracks the generated `campaign/` directory and
  its play history (init, session plans, session logs, assessments). It gitignores `.opencode/`.
  Campaign setup creates this repo and the directory structure itself (from
  `.opencode/templates/campaign/`), so the system can be started in an empty directory.

The DM agents run with the project root as their working directory, so their plain `git`
commits land in the campaign repo. Framework changes are committed in `.opencode/`.

## Constraints

- Single orchestrator model (no multi-DM support)
- Text-only (no map/visual generation)
- No real-time play integration (session-run is advisory, not a VTT)
- No automated encounter balancing (encounters are designed narratively)
- Campaign state is file-based, not queryable (no search beyond file reading)

## Non-Goals

- Virtual tabletop integration
- Character sheet *management* — no rules engine, balancing, or leveling automation. Setup helps
  with narrative character creation and records mechanical sheets as provided; building and
  leveling use existing D&D tools.
- dice rolling automation during narrative (dice tool exists separately)
- Multi-party or multi-campaign orchestration
- AI-generated battle maps or visual content
