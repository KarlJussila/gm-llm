# ORCHESTRATOR — design doc (the `orchestrator` branch)

## Why this exists
The runtime gate — the runner *calling* a `check_turn` tool each turn — is the wrong shape. A modest
model intermittently skips the tool, re-checks when told not to, and the whole multi-agent control
structure is fragile inside opencode's single-agent-with-tools TUI model. Every recurring runtime bug
traced to the same root: **deterministic control expressed through model volition.**

The fix: move the control loop **out of the model and into code.** An external **orchestrator** owns
the per-turn loop and the gate — checks always run, corrections are bounded, call pacing is central.
The model only ever does what models are good at: writing narration and adjudicating fiction.

`main` keeps the tool-gate version as a shippable "play D&D in opencode" demo. This branch is the real
architecture.

## Decisions (settled 2026-06-27)
- **Interface:** a rich terminal UI (Textual or similar).
- **Backend:** keep opencode — orchestrate over `opencode serve`'s HTTP API. Reuse the agents, skills,
  plugins, permissions, and multi-provider model routing already built.
- **Build first:** the orchestrator core (the deterministic loop), then the TUI on top, benchmark last.

## Shape
```
   ┌─────────────┐     ┌──────────────────────────┐     ┌──────────────────────┐
   │  interface  │────▶│   orchestrator core      │────▶│   opencode serve     │
   │ (Rich TUI / │     │  - per-turn loop         │ API │  - dm-runner (narrate)│
   │  benchmark) │◀────│  - deterministic gate    │◀────│  - narrative-checker  │
   └─────────────┘     │  - canon preload         │     │  - rules-checker      │
                       │  - call pacing / logging │     │  - skills, plugins    │
                       └──────────────────────────┘     └──────────────────────┘
```
The **orchestrator core** is a backend-agnostic library. The **TUI** and the **benchmark** are two
front-ends over the same core: in the TUI the player is a human; in the benchmark the player is a
scripted/model agent and the gate verdicts become scores.

## The per-turn loop (deterministic — the heart of it)
```
play_turn(player_input):
    draft     = runner.prompt(player_input)        # 1. runner drafts the turn
    verdicts  = gate(draft, player_input)          # 2. orchestrator ALWAYS runs both checkers
    if verdicts.violations:
        draft = runner.prompt(correction(verdicts))# 3. exactly ONE bounded correction pass
    log(verdicts, draft)                           #    (for the behind-screen pane / scoring)
    return draft                                   # 4. only now does the interface show the player
```
- The model never decides *whether* to check — the orchestrator does, every turn.
- Re-checking is impossible by construction: one correction pass, then send (and log if it's still
  imperfect). No loop, no doubled call volume.
- The runner shrinks to a pure function: *given player input (or correction notes), produce
  narration.* It does not "send to the player" — the orchestrator owns what reaches the interface.

## What changes in the engine (mostly subtractive)
- **dm-runner:** drop the gate step and the `check_turn` permission. The loop becomes: out-of-game? /
  in-fiction action / roll? / write narration → return. Add: "if you receive checker notes, revise
  your last narration per them."
- **dm-reminder plugin:** drop the gate step; keep the craft loop (agency / rolls / narrate).
- **turn-gate plugin:** obsolete for play. Its canon-preload logic **ports into the orchestrator**
  (Python). The plugin stays on `main` only.
- **narrative-checker / rules-checker + their skills:** unchanged. The orchestrator invokes them with
  the same briefs the plugin built (narration + player message + preloaded canon).

## Backend interaction
- Orchestrator boots (or attaches to) `opencode serve`; talks over the documented HTTP API
  (`session.create`, `session.prompt` with `agent`) — exactly what the CLI's `play` loop does.
- One persistent **runner session** for the game; **checker sessions** spawned per turn.
- Central **pacing/throttle**: the orchestrator serializes or rate-limits calls so we stop bursting
  the model's rate limit (the failure that kept killing autoplay).
- Multi-provider model choice (for the benchmark) rides on opencode's provider config.

## Build order
- **O0 — Engine prep (subtractive). ✓ DONE.** Stripped the gate from dm-runner + dm-reminder (and the
  session-run reference); runner is now narrate-and-revise.
- **O1 — Orchestrator core. ✓ DONE.** `orchestrator/` package: `backend.py` (client),
  `canon.py` (preload, ported from `turn-gate.ts`; plugin removed), `gate.py` (`Gate.check` →
  spawn both checkers, parse the `VERDICT:` line), `loop.py` (`Game`: deterministic turn → gate →
  one bounded correction), central pacing + verdict logging. Mock-tested.
- **O2 — Headless validation. ✓ built; ran live (2026-06-27).** The CLI's `play` loop (was
  `dev/autoplay.py`) drives the core with the scripted `player` agent. A 6-turn live autoplay
  confirmed the loop end-to-end (and drove the hardening pass below). `play --resume` continues the
  latest session from its transcript (reattach the live runner session if it's still up, else rebuild
  context from the transcript).
- **O3 — Rich TUI. ✓ DONE.** `tui/` Textual app: scene pane, action/meta input, toggleable
  behind-the-screen verdict pane, `/roll` + `/meta` + `/quit`, `--theme`, dracula default. Runs on
  `MockGame` offline; `--live` for the real backend.
- **O4 — Benchmark.** Swap the human for a scripted/model player; turn gate verdicts into scores;
  sweep models via opencode providers. (Shares the core; do after a live run confirms the loop.)
- **O5 — PRE planning. ✓ DONE (live run still owed).** The `Gate` generalized: `Gate.check_plan(plan)`
  reuses the spawn-and-parse-VERDICT engine, narrative-only (no conduct), canon via `CanonPreloader`
  → `PlanGateResult`. New `orchestrator/planner.py`: `Planner.prep_session(N)` drives the `dm` to
  author `session-{N}-plan.md`, gates it in code, applies **one** bounded correction, and commits
  deterministically (`campaign: session N plan`). `check-plan` skill now emits the `VERDICT:` first
  line and consumes the pre-loaded canon block (back-compatible with the dm's standalone dispatch at
  init / post-session). Entry point: `cli.py prep --session N [--commit]`. Mock-/infra-validated; the
  live model run is blocked on the same rate limit as O2.
- **O6 — POST reconcile. ✓ DONE (live run still owed).** The carried-forward Phase 5, orchestrated
  the same way as O5. `Gate.check_propagation(N)` reuses the spawn-and-parse-VERDICT engine,
  narrative-only, **no preload** (propagation is a whole-repo audit — the digest vs. the updated
  files — not a single draft) → `PropagationGateResult`. New `orchestrator/reconciler.py`:
  `Reconciler.reconcile_session(N)` drives the `dm` apply-pass (transcript → digest → author new
  canon + reconcile arc bodies → flip ledger → write state → route docs/feedback; `log-extractor` +
  `campaign-analyst` are the dm's own delegated helpers), then gates `check-propagation` **in code**
  — the gate that the skill defined but no flow ever wired — applies one bounded correction, and
  commits deterministically (`campaign: post-session N updates`). `check-propagation` skill now emits
  the `VERDICT:` line. The PRE/POST determinism is shared in `orchestrator/phase.py`
  (`apply_one_correction` — the one-correction-no-re-gate invariant — and `commit_campaign`), which
  `Planner` now also uses. Entry point: `cli.py reconcile --session N [--commit] [--prep]`, where
  `--prep` sequences reconcile(N) → prep(N+1). Mock-/infra-validated; live run owed.

## Hardening from the first live run (2026-06-27)
A 6-turn live autoplay ran (the loop works end-to-end), and surfaced three fixes:
- **Verdict at the end, not the start.** A modest checker concludes *after* working its steps, so
  forcing `VERDICT:` on the first line fought the grain — passing turns came back with no parseable
  line and fail-safed to VIOLATIONS, flagging nearly every turn. The line now goes on the checker's
  **last** line (hardened wording in all three skills + `rules-checker`), and `parse_verdict` reads
  the **last** match. Fail-safe to VIOLATIONS unchanged.
- **No runtime deltas.** The narrative-checker no longer writes `session-{N}-deltas.md`. The file was
  redundant (the checker re-reads the transcript for context anyway, and `log-extract`'s taxonomy
  already captures new-canon + plan-divergence), and worse, *stale*: the checker would flag a thing,
  the runner would change it on correction, and the logged delta no longer matched the sent turn. The
  whole deltas concept is retired — `narrative-checker` is now fully read-only; POST sources the
  **digest** alone; the `session-deltas` template is deleted.
- **Orchestrator owns the transcript.** `dm-transcript.ts` (deleted) captured the *raw* runner
  session — drafts and correction chatter included. `Game` now writes
  `campaign/sessions/session-{N}-transcript.md` from each turn's **final** messages (player + the
  corrected DM narration), since the orchestrator already holds them. Cleaner input for `log-extract`.
- **Runner context preloaded (2026-06-28).** The runner was the last agent still fetching its own
  context by tool-volition (read the plan, state, arcs, ledger at session start). Now
  `CanonPreloader.runner_preload(N)` assembles its working set in code — the **plan** plus the
  baseline canon and the entity files the plan names (no transcript tail) — and `Game.start()` /
  `resume()` inject it into the opening prompt. Same pattern as the checker preload; closes the
  resume gap (a transcript-primed fresh session had no plan). The block is framed as a head start,
  **not** a fence: `dm-runner` is told to still read/grep anything else the scene needs. `dm-runner`
  stays dual-mode — it uses the block if present, else reads the files itself (standalone use).

## How to run
One CLI dispatches every mode — `python .opencode/dev/cli.py <sub>` (the old `dev/{autoplay,prep,
reconcile}.py` are folded in and retired):
- `play --turns 6 [--resume]` — drive the gated loop with the scripted `player`. `--resume`
  continues the latest session from its transcript instead of opening a fresh scene.
- `prep --session N [--commit]` — orchestrated PRE planning.
- `reconcile --session N [--commit] [--prep]` — orchestrated POST reconcile; `--prep` chains prep(N+1).
- `tui [--live] [--theme …]` — the Textual app (mock by default; needs the venv's textual).
- `ping [N]` — N back-to-back rate-limit probes (`dev/ping.sh`).
- `bench` — stub; the O4 model-vs-model sweep lands here.

Verdict/correction blocks stream to `/tmp/orchestrator-checks.log`; the resume sidecar (the runner
session id, for reattach) lives under `.opencode/.orchestrator/` (gitignored).

## Open questions (resolve as we build)
- **Verdict parsing.** Checkers currently return prose ("PASS" or a numbered list). The orchestrator
  needs a reliable `has_violations`. Lean: require a machine-readable first line from each checker
  (e.g. `VERDICT: PASS` / `VERDICT: VIOLATIONS`) — cheap prompt change, deterministic parse.
- **Out-of-game routing.** Solve in the interface: an explicit **meta mode** the human selects, so the
  orchestrator routes the question to the runner ungated (no metagame-leakage false positive) and
  never runs the gate on it. No model-volition detection needed.
- **Correction bounding.** Exactly one correction pass; if the revision still trips the gate, send it
  anyway and log the residual. Deterministic; never loops.
- **Deltas ownership.** Keep the narrative-checker writing `session-{N}-deltas.md`, or move it into the
  orchestrator? Defer until O1.
- **Post-session reconcile** (the dm POST flow) is unchanged and out of scope for the core — see below.

## Carried forward from REFACTOR.md (still to build)
The runtime-gate refactor (REFACTOR.md) is superseded by this doc and removed; its rationale lives in
git history, and the canon/doc model it designed is now codified in the `canon-conventions` skill +
templates. Two pieces of that plan were **never built** and remain live — the orchestrator triggers
them but doesn't change their design:

- **POST reconcile (was Phase 5). ✓ built as O6.** Between sessions the `dm` runs an apply-pass,
  inline: drain `session-{N}-deltas.md` — author new-canon entity/world files + update `INDEX`, and
  **reconcile the arc bodies** (a real revision, not a status-line bump) — then write all `state/*`
  files + the PC ledger and route documents. Two delegated subagents support it: `log-extractor`
  (transcript → lossless digest) and `campaign-analyst` (assess/review) — both still the dm's own
  delegations. The **gate** (`check-propagation`), which the skill defined but no flow ran, is now
  wired by the orchestrator **in code** (`Reconciler` → `Gate.check_propagation`), not by model
  volition. Done-test (live, owed): reconcile a played session and verify nothing dropped and the arc
  body actually moved.
- **Cross-cutting (was Phase 6).** Least-privilege tool/skill allowlist audit across all agents; and a
  **model-choice** pass — checker reliability and rate limits on `mimo-v2.5-free` (now sharper, since
  the orchestrator can route checkers to a different/own-key provider).
