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
  (`session.create`, `session.prompt` with `agent`) — exactly what `dev/autoplay.py` already does.
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
- **O2 — Headless validation. ✓ built (live run still owed).** `dev/autoplay.py` drives the core
  with the scripted `player` agent. Infra-validated without model calls; **the live model run is
  still blocked on the rate limit.**
- **O3 — Rich TUI. ✓ DONE.** `tui/` Textual app: scene pane, action/meta input, toggleable
  behind-the-screen verdict pane, `/roll` + `/meta` + `/quit`, `--theme`, dracula default. Runs on
  `MockGame` offline; `--live` for the real backend.
- **O4 — Benchmark.** Swap the human for a scripted/model player; turn gate verdicts into scores;
  sweep models via opencode providers. (Shares the core; do after a live run confirms the loop.)
- **O5 — PRE planning (NEXT).** The `dm`'s planning still uses the old model-volition gating (it
  authors the plan inline, then *dispatches* `narrative-checker` `check-plan` via the `task` tool) —
  the same pattern we removed from runtime, and not driven by the orchestrator. Orchestrate it: the
  orchestrator drives the `dm` to author the plan, then runs `check-plan` **in code** (the `Gate`
  pattern generalizes — narrative-only, no conduct check; input is a plan, not a turn), applies a
  bounded correction, commits — and sequences plan → play so the orchestrator can prep a session.
- **O6 — POST reconcile.** The carried-forward Phase 5, orchestrated the same way: the orchestrator
  drives the `dm` apply-pass (drain deltas → author new canon + reconcile arc bodies → write state +
  ledger), gated in code by `check-propagation`. `log-extractor` + `campaign-analyst` support it.

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

- **POST reconcile (was Phase 5).** Between sessions the `dm` runs an apply-pass, inline: drain
  `session-{N}-deltas.md` — author new-canon entity/world files + update `INDEX`, and **reconcile the
  arc bodies** (a real revision, not a status-line bump) — then write all `state/*` files + the PC
  ledger and route documents, gating throughout with `narrative-checker` `check-propagation`. Two
  delegated subagents support it: `log-extractor` (transcript → lossless digest) and
  `campaign-analyst` (assess/review). Done-test: reconcile a played session and verify nothing dropped
  and the arc body actually moved. Under the orchestrator, this is a between-sessions run the
  orchestrator sequences (the dm-inline authoring is unchanged).
- **Cross-cutting (was Phase 6).** Least-privilege tool/skill allowlist audit across all agents; and a
  **model-choice** pass — checker reliability and rate limits on `mimo-v2.5-free` (now sharper, since
  the orchestrator can route checkers to a different/own-key provider).
