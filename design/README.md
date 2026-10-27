# design/ — what gm-llm is

This directory holds the design: **what the system is** (this file) and a design doc per
workstream. For *how to use* gm-llm, read the root `README.md`; for what remains, `ROADMAP.md`.

## File map

| Doc | What it is |
|---|---|
| [luna.md](luna.md) | The product on GPT-6 Luna — principles, agents, campaign layout, and every workflow (setup, play, combat, reconcile, planning). |
| [benchmark.md](benchmark.md) | The benchmark — the tier ladder, the run → check → grade → report pipeline, and the B-numbered stages ROADMAP orders. |
| [combat.md](combat.md) | Combat as a play mode — the tracker contract, the obligation channel, the loop, balance-as-a-skill. |
| [frontends.md](frontends.md) | The engine behind a JSON protocol, and the frontends that are its clients. |
| [findings.md](findings.md) | Frozen history (Parts 1–11) — read it for *why* an earlier call was made. No longer appended. |

## The system in one paragraph

A Python **orchestrator** lets an LLM design, run, and maintain a long-running solo tabletop D&D
campaign. Two **primary agents** split the work the way a human DM's week does: `dm` is the
between-sessions brain (setup, reconcile, planning; it writes every campaign file, delegating
focused work to the `helper` subagent) and `dm-runner` runs one live session, with read-only access
to the campaign, and then stops. The orchestrator owns every sequence — setup, play, reconcile,
planning — sending one brief per stage. Between sessions, deterministic code checks (the canon lint,
arc coverage) and the `narrative-checker`'s gates each get **at most one bounded correction**, and
code commits the result. Live play has no gate. **Skills** hold the procedures, loaded when the model
decides it needs them. All state is human-readable markdown in a **campaign repo** kept separate
from the framework repo, and what the player character knows is tracked apart from what the DM
knows, so the spoiler boundary is a data structure rather than a behavioral guideline.

The agents, the campaign layout and every workflow are in [luna.md](luna.md); combat is in
[combat.md](combat.md).

## Skills

opencode discovers skills from `.opencode/skills/<name>/SKILL.md`, so a skill's group lives in its
name, not in subdirectories:

- **`canon-conventions`** (+ templates) — the format every canon writer follows.
- **Setup:** `campaign-intake`, `world-build`, `character-create`, `character-import`,
  `arc-design`, `state-init`.
- **`*-plan`** — pulled by `session-plan` as a session needs them: `encounter-plan`,
  `investigation-plan`, `npc-plan`, `pacing-plan`.
- **Runner craft** — loaded by `dm-runner` when a scene calls for it: `social-play`,
  `discoveries`, `session-close`. The always-on table craft is in the `dm-runner` prompt.
- **`*-run`** — a play mode the runner enters: `combat-run`, with `combat-balance`.
- **Reconcile:** `apply-canon`, `apply-arcs`, `apply-state`, `feedback-curation`.
- **`check-*`** — the `narrative-checker`'s roles: `check-plan`, `check-digest`,
  `check-propagation`, `check-init`.

## The runtime seams

The parts of the design that are neither agent nor skill, and are easy to lose:

- **Fenced channels.** Every orchestrator→runner message is a user-role text part, so the
  orchestrator fences its own content in closed tags — `<prepared-context>`, `<play-so-far>`,
  `<player>`, and in a fight `<combat-turn>` / `<combat-reaction>` — keeping it distinct from the
  player's in-fiction input.
- **One session loop, whoever is playing.** `play_session` (`orchestrator/play.py`) is the turn
  loop for every player; who supplies the next message is a `PlayerSource` (the keyboard, or an AI
  player agent).
- **Frontends are clients.** The engine owns the workflow and speaks a JSON protocol; the TUI and
  the console spawn `gm-llm serve` and only render and send ([frontends.md](frontends.md)).
- **Transcripts are written by code**, to `campaign/sessions/<n>/transcript.md`, from each turn's
  player message and reply. Note-taking never depends on the model.
- **Warm threads, compacted when full.** The `dm` keeps one thread from setup or reconcile
  through the next plan, and the runner one per game session. opencode's auto-compaction is on:
  past the model's input ceiling it summarizes the thread's history and the thread carries on.
  The record never depends on it — transcripts are written by code and canon lives in files.
- **Completion is a disk fact.** When the runner ends a session (`task_complete`), the orchestrator
  records it under `.opencode/.orchestrator/session-<n>.json`, so a session closed before the wrap
  reopens to the same wrap-or-quit choice instead of resuming into more play. Setup and reconcile
  keep per-stage markers there too, so a failed pass resumes where it died.
- **Dice** are the `dice` opencode plugin, not model arithmetic.
- **Git commits are code-owned.** The orchestrator commits at phase boundaries (`campaign: init`
  / `session N plan` / `post-session N updates`); the model never runs git in an orchestrated
  pass.

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
- **Not a real-time play integration.** The runner's table craft is guidance for a model, not a
  table automation layer.
