# design/ — what gm-llm is, and the plans of record

This directory holds the design: **what the system is** (this file) and a plan-of-record doc
per workstream. `tools/lint_docs.py` check 1 fails if a doc here is not linked from the file
map below, so add the row when you add the doc.

For *how to use* gm-llm, read the root `README.md`. For the current state of the work, read
`HANDOFF.md`; for what remains, `ROADMAP.md`.

## File map

| Doc | What it is |
|---|---|
| [benchmark.md](benchmark.md) | Plan of record for the benchmark workstream — the tiered instrument, the B-numbered stages ROADMAP sequences, measurement methodology, risks. |
| [combat.md](combat.md) | Plan of record for combat as a runner play-mode — the tracker contract, the obligation channel, the loop, balance-as-a-skill. |
| [frontends.md](frontends.md) | Plan of record for frontend/mode modularity — watching autoplay and bench runs in the TUI. |
| [luna.md](luna.md) | Plan of record for the Luna-targeted Tier-1 product — its clean-slate boundary, discovery slice, and product shape. |
| [runner-authority.md](runner-authority.md) | Tier-0 reference — the MiMo runner-authority model and the partially landed recalibration that Tier 1 deliberately does not inherit. |

### Working docs (not the design — the project's own state)

| Doc | What it is |
|---|---|
| [findings.md](findings.md) | The append-only round archive — one Part per round. Point-in-time; read it for *why* a call was made. |
| [open-questions.md](open-questions.md) | The live backlog of unresolved decisions and known gaps. Resolved items are deleted, not tombstoned. |

## The system in one paragraph

The currently shipped Tier-0 profile lets a modest LLM design, run, and maintain a long-running
solo tabletop D&D campaign.
Two **primary agents** split the work the way a human DM's week does: `dm` is the
between-sessions brain (it authors every campaign file — world, arcs, character files, session
plans, the post-session apply) and `dm-runner` runs one live session and then stops. Neither
does the other's job, and that bar is written into both prompts. A Python **orchestrator** owns
every sequence — the gated per-turn loop, the staged setup, PRE-session planning, and the
staged post-session reconcile — dispatching one focused brief at a time, each verified by a
`check-*` role of the `narrative-checker` subagent or by a deterministic lint, with **at most
one bounded correction** and a **code-owned git commit**. The model never decides whether or in
what order steps happen. **Skills** hold the actual procedures, one home per rule, loaded on
demand. All state is human-readable markdown in a **campaign repo** kept separate from the
framework repo, and what the player character knows is tracked separately from what the DM
knows — so the spoiler boundary is a data structure rather than a behavioral guideline.

The next product profile is Tier 1, targeted at Luna. It keeps the code-owned campaign and runtime
substrate but re-authors the model-facing behavior from first principles; see [luna.md](luna.md).
The architecture below describes the shipped Tier-0 profile, not a mandatory topology for Tier 1.

## Architecture

**Primary agents** — the player starts whichever phase they are in:

- **`dm`** — the between-sessions brain. Authors every campaign file itself: world, arcs, the
  character files, session plans, and the post-session apply. It does **not** run live sessions,
  and it works one orchestrator-dispatched brief at a time (setup stages, apply stages, prep).
- **`dm-runner`** — runs one live session (narration, NPCs, improvisation, dice), then stops. It
  does **not** take notes, plan, assess, or adjust arcs (the transcript is auto-captured).

**Subagents** (`mode: subagent`, spawned by the orchestrator as their own sessions, never
started by the player): `campaign-analyst` (post-session assessment + player-feedback curation —
it writes only its own deliverables, never canonical state), `log-extractor` (transcript →
digest), and the verification agent `narrative-checker`. The checker is a thin wrapper that
loads one of its role skills (`check-turn` + `check-conduct` at runtime, `check-plan` /
`check-digest` / `check-propagation` / `check-feedback` / `check-init` between sessions,
`check-combat` in a fight), works the role's checks, and submits its verdict via the
`report_findings` tool (the shared protocol lives once in the agent prompt). At runtime the
canon and conduct checks run in one warm session — conduct benefits from the canon/ledger
context the canon check just loaded.

**Orchestration.** `gm_llm/orchestrator/` — plain Python over `opencode serve`'s HTTP API — owns
every sequence: the gated per-turn loop, the staged setup, PRE-session planning, and the staged
post-session reconcile (digest → assessment → feedback → canon → one dispatch per arc → state →
propagation check → commit → prep). Every stage is one focused brief, checked by the matching
`check-*` role or a deterministic lint. Stage markers make a failed pass resume where it died.

**Skills** (procedures, reused by both agents and subagents):

- **Authoring contract:** `canon-conventions` (+ templates) — file shapes, slugs, `[[links]]`,
  the registry, awareness flags, the required `## Vitals` completeness block.
- **Setup:** `campaign-setup` (cross-cutting standards), `campaign-intake`, `world-build`,
  `character-create`, `character-import`, `arc-design`, `state-init`.
- **Planning:** `session-plan`, plus the focused `*-plan` skills below.
- **Live play:** `session-run`, `session-flow`, `session-close`, `social-play`, `discoveries`.
- **Post-session:** `log-extract`, `session-review`, `apply-canon`, `apply-arcs` (one arc per
  dispatch), `apply-state`, `feedback-curation`.
- **Checks:** the `check-*` role skills of the narrative-checker.

**Session-level skills come in groups, by a flat naming convention** (opencode discovers skills
from `.opencode/skills/<name>/SKILL.md`, so the type lives in the name, not in subdirectories).
Many table concerns — investigation, NPCs, encounters, pacing — have both a *planning* face and a
*running* face, and the content differs between them:

- **`*-plan` skills** — pulled by `session-plan` when designing a session: `encounter-plan`,
  `investigation-plan`, `npc-plan`, `pacing-plan`. Planning is deliberate and sectioned, so
  these load as needed.
- **Runner craft skills** — the live craft `dm-runner` loads each session. `session-run` is the
  always-on core (agency, rolls, spoilers, applied every turn); it loads companions as the scene
  calls for them — `session-flow` (open / pace, and the judgment of when to end),
  `session-close` (ending, level-up, feedback, wrap — loaded when pacing says it's time),
  `social-play` (conversations and playing NPCs), `discoveries` (revealing information).
- **`*-run` skills** — a distinct *play mode* `dm-runner` enters, as opposed to the
  always-resident craft above: `combat-run` (see [combat.md](combat.md)).

The setup and post-session skills are neither — they are the between-session procedures the
orchestrator dispatches to the `dm` (authoring), the `campaign-analyst` (analysis + curation),
and the `log-extractor` (extraction).

**Boundaries that prevent role bleed:**

- The two roles are separate primary agents; the player starts whichever phase they're in.
- `dm` is explicitly barred from running sessions; `dm-runner` is explicitly barred from
  planning, assessing, and arc work.
- Post-session work belongs to the between-session pipeline: the runner just plays (the
  transcript is auto-captured, its handoff notes filed by code), and the pipeline extracts,
  assesses, and applies fresh between sessions.
- **Spoiler discipline:** the human is the player and has not read the planning files. Both
  primary agents keep spoiler-bearing content (upcoming beats, twists, NPC secrets) in files and
  out of conversation, narrating only what the character can perceive.

## Knowledge and awareness

What the player character knows is tracked separately from what the DM knows, so the boundary is
a data structure rather than a behavioral guideline:

- A live PC knowledge ledger (`characters/{name}-knowledge.md`) — Knows / Believes (incl.
  misinformation) / Open questions — read at session start and updated as the character learns.
- Awareness flags on stored facts (`[hidden]` / `[revealed: S<n>]`) with a `Known to:` list of
  the in-world parties aware of each secret — so NPCs act only on what they know, and
  information can spread.
- Session plans flag each clue/reveal as known, a new reveal, or staying hidden, sourced from
  the ledger.

## The runtime seams

The parts of the design that are neither agent nor skill, and are easy to lose:

- **Fenced control channels.** Every orchestrator→runner message is a user-role text part
  (opencode distinguishes only system from user, not kinds of user content), so the orchestrator
  fences each of its channels in closed tags — `<turn-reminder>`, `<player>`, `<correction>`,
  `<prepared-context>`, `<play-so-far>`, `<session-length>` — keeping its own instructions
  unambiguously distinct from the player's in-fiction input.
- **Per-turn craft reminder.** The orchestrator prepends the runner's per-turn DM *craft* loop
  (agency, ask-for-a-roll, narrate-the-response) to each player message, so the craft stays
  salient and resists decay over a long session.
- **One session loop, whoever is playing.** `play_session` (`orchestrator/play.py`) is the turn
  loop for every frontend and every player; who supplies the next message is a `PlayerSource`
  (keyboard or the scripted `player` agent) and what renders it is a set of hooks. It blocks, so
  an async frontend runs it on a worker thread and feeds the source from its own — which is how
  the TUI can render an unattended run ([frontends.md](frontends.md)).
- **Automatic transcript capture.** The orchestrator writes
  `campaign/sessions/session-{N}-transcript.md` from each turn's final messages (player +
  corrected DM narration). Note-taking never depends on the model.
- **Live-session context management.** The runner reuses one warm session for a whole game
  session. opencode's own auto-compaction — a single LLM summarization pass that would lossily
  rewrite canon — is disabled (`OPENCODE_DISABLE_AUTOCOMPACT`); instead, once the session
  reaches opencode's compaction threshold, the orchestrator counts down a `<session-length>`
  nudge steering the runner to end at a clean beat (explicitly *without* rushing the story — an
  odd stopping point beats a hurried one). No live narration is ever summarized by a model.
- **Session completion is a disk fact.** When the runner ends a session (`task_complete`), the
  orchestrator records it under `.opencode/.orchestrator/session-{N}.json`, so a session the
  player closed the app on without confirming the wrap reopens to the same wrap-or-quit choice
  instead of resuming into more play.
- **Subagent invocation** is one `opencode serve` session per subagent over the HTTP API — no
  `task`-tool delegation, no `opencode run` subprocess.
- **Dice** are the `dice` opencode plugin, not model arithmetic.
- **Git commits are code-owned.** The orchestrator commits at phase boundaries (`campaign: init`
  / `session N plan` / `post-session N updates`); the model never runs git in an orchestrated
  pass. The DM agents run with the project root as their working directory, so their plain `git`
  commits land in the campaign repo, not the framework's.

## Constraints and non-goals

Deliberate scope boundaries — a request that runs into one of these is answered "no", not filed
as a gap:

- **Single orchestrator model.** No multi-DM support; no multi-party or multi-campaign
  orchestration.
- **Text only.** No maps, no visual generation, no VTT integration.
- **No rules engine.** Character sheet *management* is out: no leveling automation. Setup helps
  with narrative character creation and records mechanical sheets as the player provides them;
  building and leveling use existing D&D tools. (Combat's tracker is bookkeeping for a fight in
  progress — hp, conditions, position — not a rules engine; see [combat.md](combat.md).)
- **No automated encounter balancing.** Encounters are designed narratively. `combat-balance` is
  craft prose about action economy and rounds-to-kill, deliberately *not* CR or XP-budget math —
  those are calibrated for a ~4-PC party and mislead in a single-PC game ([combat.md](combat.md)
  § Balance).
- **Campaign state is file-based, not queryable.** No search beyond file reading.
- **Not a real-time play integration.** `session-run` is craft guidance for the runner, not a
  table automation layer.
