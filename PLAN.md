# PLAN — between-sessions rework (the `orchestrator` branch)

This is the active design/plan doc. It supersedes `ORCHESTRATOR.md`, whose plan
(O0–O6: orchestrator core, runtime gated loop, PRE planning, POST reconcile, TUI)
is built — that build history lives in git. `SPEC.md` describes what the system
*is*; this doc describes the work in flight.

## The one principle (unchanged since the pivot)

**Deterministic control in code; generative work in agents.** The orchestrator owns
*sequencing and the dispatch of each task brief*; agents author. Every unit of work is
the same shape as a runtime turn:

```
dispatch one focused brief  →  specialized check (narrative-checker task, or a
deterministic lint)  →  at most ONE bounded correction (never a re-gate loop)  →
checkpoint
```

The model never decides *whether* or *in what order* to do the steps — code does. The
two invariants that keep this safe (one correction, code-owned git) live in
`orchestrator/phase.py` and are shared by every phase. Because the engine targets a
**modest model**, the win is structure over smarts: five small, individually-verifiable
dispatches beat one ten-part marathon whose quality decays before the end.

## Foundation (built — don't redo)

`orchestrator/` is a backend-agnostic core over `opencode serve`'s HTTP API:
- `backend.py` — client; central pacing; cancel/revert; per-call timeout.
- `canon.py` — `CanonPreloader` (canon + entity preload, in code).
- `gate.py` — one `narrative-checker` agent, specialized task-skills:
  `check()`/`check_plan()`/`check_propagation()`; report-only, `VERDICT:` parsed from
  the **last** line, fail-safe to VIOLATIONS.
- `loop.py` — `Game`: the deterministic per-turn loop; owns the transcript and the
  per-turn reminder injection.
- `phase.py` — `apply_one_correction` (the one-correction invariant) + `commit_campaign`
  (code-owned git).
- `planner.py` / `reconciler.py` — PRE/POST phases over `phase.py`.
- `tui/app.py` — Textual app: scene pane, behind-the-screen pane, action/meta input,
  cancel/revert.
- `stream.py` — `EventTap`: live `/event` SSE view (`--stream`).
- `dev/cli.py` — one dispatcher: `play` / `prep` / `reconcile` / `tui` / `ping` / `bench`.

## The problem this rework fixes

Runtime feels polished because it's deterministic sequencing in code. The **post-session
pass is the opposite**: `reconcile_session` makes ONE fat `dm` call (`_APPLY_BRIEF`) that
asks the model to self-sequence ~8 jobs by volition — extract digest, author entities,
register rows, revise arcs, flip ledger, update every state snapshot, route documents,
distill feedback — then gates the whole blob once. That is exactly the self-dispatching
call the pivot pulled out of runtime, one stage out. Observed consequences:

- **The analyst fell out.** `campaign-analyst` (intact; its high-value assessment fed the
  dm's adjustments) was only ever a *dm-volition delegation* inside the fat brief — and the
  dm stopped reliably calling it.
- **Entities come out under-fleshed.** `entity-npc.template.md` has deep narrative sections
  but **no required structured vitals** (race/species, surname, pronouns, affiliation) — so
  a file is "complete to template" yet missing a last name; the runner improvises the hole
  mid-session → checker flags + stalls.
- **Feedback is ham-fisted.** The dm dumps the player's verbatim feedback into the matching
  file rather than curating standing guidance.
- **No per-stage verification, no resumability.** One blob → you can't tell which job failed;
  a mid-pass failure re-runs the whole non-idempotent apply (the bug we hit).

## The staged pipeline (core of the rework)

Decompose the one fat brief into ordered, orchestrator-dispatched stages. Each stage:
dispatch → specialized check → ≤1 correction → checkpoint. Threads in brackets.

| # | Stage | Thread / agent | Check after | New? |
|---|-------|----------------|-------------|------|
| A1 | Collect player feedback (in-fiction) | runner (live ctx) | — | the TUI "end session" is the long-missing session-end signal |
| A2 | Session notes — player decisions, new/changed entities, threads opened, what mattered | runner authors → **code writes** `session-{N}-notes.md` | — | runner stays no-write; orchestrator dispatches + files |
| B | Digest transcript → `session-{N}.md` | log-extractor | **check-digest** — faithful to transcript: no invented beats, nothing load-bearing dropped | **NEW task** |
| C | Assessment → `assessment/session-{N}-assessment.md` (consumes digest **+ runner notes** + state/arc) | campaign-analyst | — (analysis, not canon) | analyst **promoted to a first-class stage** |
| D | Apply canon — author/register entities **to the completeness contract**, revise arc bodies, flip ledger, update state; fed C's assessment | dm | **check-propagation** (sharpened) **+ deterministic completeness lint** | exists + code lint |
| E | Curate feedback → `campaign/feedback/*` (player feedback + runner notes, deduped/superseded standing guidance — not a verbatim dump) | campaign-analyst (continues C) | **check-feedback** — faithful to the player's ask, routed right, campaign-agnostic | **NEW task** |
| F | Plan session N+1 | **same dm thread as D** (warm context) | **check-plan** | exists |
| G | Commit; ready to start N+1 | code | — | — |

The **analyst is the linchpin**: it reads the session once (C), then both informs the dm's
canon adjustments (D) and curates feedback (E) — curation is synthesis (its job), not filing
(the dm's). Stage E is independent of D/F; run it sequentially in v1.

## Cross-cutting changes

1. **Entity-completeness contract.** Add a required *identity-at-a-glance* block to the entity
   templates (NPC: canonical name incl. surname, race/species, pronouns, age band,
   role/affiliation; mirror per type: location→region/settlement-type, item→type/owner, …).
   Enforce two layers: a cheap **deterministic lint** (required fields present?) + the
   narrative checker (do the committed values cohere with the rest of canon?). This helps
   live play and prep immediately, not just reconcile.
2. **Analyst promoted** to stages C + E (no longer a dm delegation by volition).
3. **Runner session notes** (A2): orchestrator dispatches the brief, runner authors the prose,
   **code writes the file** — keeps the runner narration-pure.
4. **New checker tasks:** `check-digest`, `check-feedback`, each a report-only skill with the
   `VERDICT:` line last + fail-safe; `Gate` grows `check_digest()` / `check_feedback()`
   mirroring the existing methods.
5. **Same-thread prep:** F reuses D's dm thread for warm context. Tension with modest-model
   context decay → mitigate by keeping D decomposed (sub-dispatches) rather than one giant
   apply turn, so the thread isn't bloated before planning.
6. **Feedback curation** is analyst-owned and `check-feedback`-guarded (fixes the verbatim dump).

## TUI unification

Trigger the whole lifecycle from one screen: wrap session → reconcile (staged) → prep(N+1) →
play(N+1).
- **Scene pane** → minimal, spoiler-free **step ticker** (`Reconciling session 1 ▸ filing new
  canon (4/7) ▸ …`).
- **Behind-the-screen pane** → the **full `EventTap` stream**. Required change: `EventTap`
  currently writes to `sys.stdout`; it must emit to a callback/queue so the pane renders it.
- A **phase controller** drives runner → log-extractor → analyst → dm across the pipeline, then
  hands to `Game` for N+1; the input bar is repurposed per phase.

## Resumability

Checkpoint after each stage so a failure resumes at the failed stage, not a whole non-idempotent
re-run (the retry hazard we hit — the big per-call timeout is only a band-aid). Design every stage
re-entrant. v1 may land the clean decomposition first and layer durable checkpointing after, but
stages are written to make that cheap.

## Build order (slices)

- **(i) Entity-completeness contract** — templates + deterministic lint + checker leans on it.
  Independent of the pipeline; improves live play and prep right away. Do first.
- **(ii) Staged reconcile pipeline** — stages B–F: analyst promoted (C), runner notes (A2),
  `check-digest` + `check-feedback`, same-thread prep (F), per-stage checkpoints.
- **(iii) TUI unification** — phase controller + `EventTap` callback; full lifecycle in one screen.

## Settled decisions

- **Feedback owner = `campaign-analyst`** (after its assessment), not a new agent.
- **Same-thread prep = yes** (warm context); decompose D if the thread bloats.
- **`check-propagation` stays whole for v1**; split to match if D is decomposed into
  entity / arc / ledger+state sub-dispatches.
- **`check-digest` + `check-feedback`** are the new checker tasks; completeness is a deterministic
  lint *plus* the narrative checker, not either alone.

## Backlog (deferred — not blocking the slices above)

Slices (i)–(iii) are built and slice (ii) was live-validated; the prompt rehome, the
`session-review` rewrite, the `dm.md` POST-flow repoint, and the `arc-design` Model-B review are
done (history in git). Remaining:

- **PC-side / init refactor.** The PC entity gets no Vitals contract yet (`type: pc` is skipped by
  the lint). The player-facing init flow (character creation, campaign setup) is its own larger
  refactor the player flagged as next after this one — fold a PC vitals/stat contract into it then.
  Init already authors the major arc + optional minor arcs (Model B); the open piece here is the PC
  contract and the creation flow itself.

## Done-tests

- (i) An NPC authored to the new template carries every required identity field; the lint fails a
  file missing one; a played session no longer flags "no surname / no race" mid-turn.
- (ii) A full `reconcile --session N` runs each stage as its own dispatch, the analyst assessment
  exists and is consumed by the apply, feedback files read as curated standing guidance (not a
  verbatim dump), and each stage's specialized check ran in code.
- (iii) From the TUI: end a session, watch the step ticker advance with full logs behind the screen,
  then start session N+1 — without leaving the app.
