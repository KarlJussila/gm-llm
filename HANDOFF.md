# HANDOFF — orchestrator branch (working notes)

Cold-start context for continuing the orchestrator work. Design-of-record is
`ORCHESTRATOR.md`; this is the "where we are / what's next / gotchas" companion.

## Where we are
- Branch **`orchestrator`**. `main` = the shippable "play D&D in opencode TUI" demo (the old
  tool-gate version, untouched).
- **Done:** O0 (strip runtime gate), O1 (orchestrator core), O2 (autoplay driver — built, infra-only),
  O3 (rich TUI). See ORCHESTRATOR.md build order.
- **NEXT: O5 — integrate PRE planning with the orchestrator.** (O4 benchmark and a live run come
  later; O6 is POST reconcile.)

## The pivot in one paragraph
The runtime gate used to be a tool the runner *called* each turn; the modest model skipped it and
re-checked unpredictably. We moved the control loop out of the model into an external **orchestrator**
(Python) that drives play deterministically over `opencode serve`'s HTTP API. The runner shrank to
"draft + revise-on-notes." Goals: a seamless rich-TUI play experience **and** a model-vs-model
benchmark, both on the same core.

## Architecture / key files (all on the branch)
- **opencode backend** (unchanged): `opencode serve` hosts the agents/skills/plugins. The
  orchestrator talks to it over HTTP (session.create, session.prompt with `agent`).
- **`orchestrator/`** — the core (dependency-free except the backend client):
  - `backend.py` — `Backend`: start/attach serve, `create_session`, `prompt(session, agent) → text`.
    Throttle handling lives here: `turn_timeout=360` (rate-limited calls *hang*, don't error),
    retry/backoff, `min_call_gap` pacing. `on_retry` callback.
  - `canon.py` — `CanonPreloader(dir).build(draft)` → the "PRE-LOADED CANON" block (INDEX parse,
    full+partial name match, baseline + matched-entity + transcript-tail). Ported from the (now
    deleted) `turn-gate.ts`.
  - `gate.py` — `Gate(backend, preloader).check(narration, player_msg) → GateResult`. Spawns
    `narrative-checker` (check-turn) + `rules-checker`, parses the `VERDICT: PASS|VIOLATIONS` first
    line (fail-safe to VIOLATIONS). `GateResult.violations`, `.correction_brief()`.
  - `loop.py` — `Game.start()/turn()/meta() → TurnResult`. Deterministic: draft → gate (always) →
    **one** bounded correction (no re-gate) → return. `meta()` is ungated. Logs verdict blocks to
    `/tmp/orchestrator-checks.log`.
  - `mock.py` — `MockGame`: offline scripted TurnResults (cycles clean/corrected) for UI/tests.
  - `__init__.py` — exports `Backend, CanonPreloader, Gate, Game, …`.
- **`tui/`** — Textual app: `app.py` (`PlayApp`), `__main__.py` (entry). Scene + behind-screen panes
  (scrollable **Static**, selectable), action/meta input, `/roll` `/meta` `/quit`, `--theme`
  (dracula default), `--live`. Runs on `MockGame` by default.
- **`dev/autoplay.py`** — headless driver: boots `Backend`, builds `Game`, drives it with the
  scripted `player` agent, streams DM + verdicts.
- **Engine changes vs main:** `dm-runner.md` (no `check_turn`/gate; narrate-and-revise),
  `dm-reminder.ts` (gate step removed), `session-run` (checker-gate refs scrubbed), `check-turn`
  skill + `rules-checker` (emit `VERDICT:` line), `turn-gate.ts` **deleted**, `REFACTOR.md`
  **deleted** (→ ORCHESTRATOR.md; rationale in git history).

## How to run
- venv: `.opencode/.venv` (textual 8.2.7; Python 3.14). `.venv/` is gitignored.
- **TUI (offline mock):** `cd .opencode && .venv/bin/python -m tui` (`--theme tokyo-night`, `--live`).
- **Autoplay (live; needs rate limit clear):** `python3 .opencode/dev/autoplay.py --turns 6`.
- **D&D Beyond scraper:** `~/.local/bin/ddb-sheet <id|url>` (generic; not in the repo).

## Blockers / state
- **RATE LIMIT (open):** `mimo-v2.5-free` has been throttled for hours from heavy autoplay. **No
  live model run has validated the loop end-to-end yet** — it's mock-proven and infra-validated only.
  Either wait for the cap to clear, or route the agents to a model with real quota (the cross-cutting
  "model choice" item). A rate-limited call *hangs* up to `turn_timeout` then retries.

## NEXT — O5 (PRE planning), implementation notes
- Today the `dm` authors the plan inline (`session-plan` skill) then **dispatches** `narrative-checker`
  `check-plan` via the `task` tool — model-volition, not orchestrated.
- Target: orchestrator drives the `dm` to author the plan for session N, then runs `check-plan` **in
  code**, applies a bounded correction, and the dm commits the plan file. Then sequence plan → play.
- `Gate` is hardcoded for check-turn (2 checkers + player_msg). **Generalize it:** check-plan is
  narrative-only (no conduct), input is a *plan* (no player_msg). Likely a `Gate.check_plan(plan)` or
  a sibling function reusing the spawn-and-parse-VERDICT machinery; feed it canon via `CanonPreloader`.
- Decide who writes `campaign/sessions/session-{N}-plan.md` — keep the `dm` writing it (it has
  write/edit), orchestrator triggers + gates. Add a "prep session N" entry point (orchestrator method
  + a dev script / TUI affordance).
- O6 (POST reconcile) follows the same shape with `check-propagation` (see ORCHESTRATOR.md
  "Carried forward").

## Gotchas (don't relearn these)
- **Build-agent trap:** the opencode TUI defaults to the `build` agent; if a session isn't explicitly
  `dm-runner`, none of the runtime machinery engages (this caused a "DM stopped checking" red
  herring). The orchestrator forces the agent via the API, so it's immune.
- **`RichLog` is not text-selectable** (renders opaque strips) — use `Static` for selectable panes.
- **Rate-limited calls hang**, they don't error — hence the short `turn_timeout` + retry.
- **`dm-reminder`** re-injects the per-turn craft loop via `experimental.chat.system.transform`,
  which fires in the core LLM request path (works for API-driven prompts too).
- Two git repos: `.opencode/` (engine) and the campaign root (gitignores `.opencode/`). Commit only
  when asked; sentence-case imperative subject; **no attribution trailer**.
- Memory: `orchestrator-pivot.md` (current), `campaign-engine-refactor.md` (superseded history).
