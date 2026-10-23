# Changelog

All notable changes to gm-llm are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project uses `0.x` versioning
(minor = a feature set or new mode, patch = fixes and small changes — see `CLAUDE.md`).

There is no PyPI publish: a "release" is the version-bump commit, which live campaigns pick up via
`pipx reinstall` + `gm-llm update`. The single source of the version is `gm_llm/__init__.py`.

## [Unreleased]

### Added
- **Frontends are clients of an engine.** The campaign workflow moved out of the TUI into an
  engine that speaks JSON lines over stdio (`gm-llm serve`); the TUI and the console spawn it
  and only render and send, so a frontend can be written in any language
  (`design/frontends.md`). `play --ui console` is a plain-text frontend for a human player too.
- `gm-llm tokens --sessions` lists a campaign's opencode sessions with their wall and model time,
  peak context and the skills they loaded; `--session N` prints one step by step with its tool calls.
- **`create_entities`**, a tool that writes many new entity files in one call from their
  templates, with their state files; it checks every spec first and never overwrites.
- Setup writes the player a spoiler-free primer, `campaign/documents/primer.md`.

### Changed
- **The model-facing prompts are rewritten for GPT-6 Luna.** Briefs state the goal, not the skills
  to load; skill descriptions say only when to load them; no prompt instructs a task list. The
  in-play check skills (`check-turn`, `check-conduct`, `check-combat`) are deleted, and
  `combat-run` now says to roll initiative before `start_encounter`.
- **The autoplayer's character packet is generated** from the PC's sheet, state and knowledge
  ledger, the same way for `--player auto` and `bench run`; the sheet's DM-side hooks stay out.
  `--character` and the `*.player.md` lookup are gone. The autoplayer gets no per-turn reminder:
  `player-rolls` and `player-combat` are skills only it can load.
- **Campaign setup builds the world in its own stage.** The DM pitches a world the player can
  revise; once they approve it, a non-interactive stage builds it top down — the world in broad
  strokes, the region in structure, the vicinity where the character begins in fine detail — and
  writes the primer. Character hooks come from the built world, and arcs are cast from named NPCs.
  Arcs and initial state are authored in one dispatch, checked from disk with one correction and
  resumable after interruption. The canon lint handles structural checks; `check-init` reviews
  coverage of each tier, casting, duplicates and consistency. The `campaign-setup` skill is removed.
- **Anyone of consequence is named and filed** as soon as it's apparent they'll matter; only a
  one-off extra stays unnamed. An NPC starts as a shim — vitals, who they are, what they want — and
  the lint no longer requires stats of one, nor `check-init` a hidden layer on every entity.
- **A cut-off model call is resumed, not reverted.** A stall, an error or the time limit used to
  throw the attempt away and send the prompt again; now the retry tells the agent to carry on in
  the same session, so a long authoring stage keeps the work it did. Each failed attempt is a
  `retry` event in the archive.
- **Threads are the leads beside the arcs**, including the vicinity's own problems; the threads
  dashboard says where each stands, and one the player takes up can become a minor arc.
- Player feedback lives outside the campaign in a shared player directory. The runner receives
  its standing guidance in prepared context, and agents read matching feedback when loading skills.
  Benchmark runs use private copies of the fixture's feedback. The agents work on a copy in the
  project's `feedback/`, which gm-llm fills from the player directory and copies curation back
  from, so they no longer need access outside the project.
- **Check results reveal details, not conclusions** (`discoveries`). A roll yields what the
  character observes, and for a knowledge skill what they'd generally know, arranged so the
  conclusion appears likely; a conclusion no such arrangement supports isn't handed over, however
  high the roll.
- **Every fact has one home.** `canon-conventions` § What goes where maps each kind of fact to its
  file. A place's files hold who is based there, never who is there now or who came and went;
  `check-propagation` flags a fact copied onto another entity's file.
- The dice tool no longer tells the DM who rolls on every call.
- **A campaign runs apart from the player's own opencode setup.** The server starts with an empty
  stand-in for the global config directory, so a personal `AGENTS.md`, MCP servers, plugins and
  skills stay out, and each agent's permissions allow only its own skills: the runner no longer
  sees the checkers' skills, nor the checkers the planners'.
- **Requires opencode 2.1 or newer.** The backend speaks opencode's v2 server API (opencode 2.0
  dropped the v1 API), and the plugins use the v2 plugin contract, which needs no npm install:
  `gm-llm init` no longer installs plugin dependencies, and `gm-llm update` removes the
  `package.json` and `node_modules` older versions left in `.opencode/`. On Windows the installer
  now installs opencode from `@opencode/cli`.
- **`bench grade` confirms or rejects the checker's findings.** One `grader` session per run (Sol
  at `high`) takes the run's `checks-<run>.jsonl` findings and the flagged stage gates in play
  order, with the campaign before and after the run and its transcript to read, and confirms or
  rejects each against rubric v2; only confirmed findings score. A run that hasn't been checked
  is skipped, and `bench report` flags it. The report adds checker and gate precision and the
  stage correction rate; the defaulted rate now counts checked turns with no submission. A gate's
  correction reaches the grader as a diff, apart from the draft the gate judged.

### Added
- **`bench check`** — the after-play checker. One rolling `play-checker` session per run reads
  the archived turns in play order against the campaign as it stood before play, and writes each
  turn's canon, conduct and combat findings to `checks-<run>.jsonl` beside the archive.
- **`bench status`** lists a batch's runs by where they stand — complete, reconcile pending,
  resumable, capped — read from the archives the way `--resume` reads them. `bench check` and
  `bench grade` skip a run that isn't finished, and `bench run` exits non-zero unless every run
  finished.
- **Archived turns record the DM's own dice rolls** (`rolls`: expression and total), and the
  checker sees them.
- `gm-llm tokens` counts the checker's workspace (`check-ws`) as its own scope beside grading.
- **A campaign can play on any model.** `model` and `variant` in `gm-llm.yaml` run every agent,
  the subagents included, on another model or reasoning variant, without editing the agent
  files, so `gm-llm update` keeps the choice. `gm-llm play --model` / `--variant` override them
  for one invocation, as do `dev autoplay`, `dev prep` and `dev reconcile`.
- **`bench run --subject-model` / `--subject-variant`** run the subject agents (`dm-runner`, `dm`,
  `author`, `log-extractor`) on another model; `--tier` names the scaffolding tier (`low`, the
  product, is the only one yet). The `conditions` event stamps every agent's model and reasoning
  variant (no longer a temperature) and the `subagents` mode, and the report keys on them.
- `gm-llm.yaml` configures `feedback-dir`, `subagents: sequential | parallel`, and optionally
  `model` and `variant`. `gm-llm init` and `update` write the defaults if the file is missing,
  and never overwrite it.
- **Each archived turn records the tools the runner called while drafting it** (`tools`), so
  whether a session was played from canon or from memory is readable without the grader.
- **`bench report` states its own precision.** The integrity score now carries a 95% confidence
  interval on the batch mean and a *resolution* figure — the smallest difference a batch that size
  could tell apart. The multiplier is Student's t rather than the normal 1.96, because a batch
  estimates its spread from the same few runs it averages; at five runs that surcharge is 42% of
  the interval, so the old hand-computed figures were optimistic. Dimension subscores built on
  fewer than ten violations batch-wide are now flagged rather than printed as measurements: a
  subscore over one or two severity labels inherits the grader's full per-label disagreement with
  nothing to average it against.
- **The grading instrument is fingerprinted (`bench grade`, `bench report`).** A grades file's
  rubric version was a hand-typed label, and a label does not move when the prose under it is
  rewritten in place — `rubric-v1.md` has already been reworked once (penalty table, binding
  categories, wider dedup window) with every grades file on both sides still reading `v1`.
  Grade headers now carry a content hash over the whole instrument (rubric, grader brief,
  `submit-grade` schema), the way a run's header already hashes the prompts it played. Two
  consequences: re-grading after sharpening the rubric no longer silently skips every run as
  "already graded", and `bench report` flags a batch scored by more than one instrument instead
  of pooling it. Grades written before the fingerprint existed are grandfathered rather than
  invalidated.

### Fixed
- **Deleted assets no longer ship from a stale `build/`.** setuptools reuses the clone's `build/`
  and never prunes it, so skills removed in the Luna rework still installed and the agents loaded
  them. The Windows installer now clears it, and the manual update says to.
- **Slow model calls are no longer cut short.** A call now counts as stalled only after 10 minutes
  without output (was 3), and play, setup and wraps get 30 minutes per call (was 6, which a
  big setup or reconcile call could outlast).
- **A reveal no longer splits a wrapped `Known to:` line.** The PC was added to the entry's first
  line, mid-sentence; it now goes at the end of the entry.
- **Setup no longer shows the DM's message twice.** Luna can say a line as commentary before a
  tool call and repeat it as its final answer; a reply is now its final answer when it has one.
- **A turn that ends on a tool call no longer loses its narration.** opencode splits a turn at each
  tool call and returns only the last message, so prose written *before* a trailing tool call came
  back empty — a blank scene to the gate and the player. The draft is now recovered from the
  session history.

## [0.5.0] — 2026-07-29

### Added
- **Watch a benchmark batch in the TUI (`bench run --ui tui`).** A batch header tracks run *k*
  of *N* and the outcomes so far, and each run's play — turns, gate verdicts, fights, the
  post-session reconcile's stage ticker — renders in the scene pane as it would in a live
  session, with the model stream behind `ctrl+g`. Watching is deliberately read-only: nothing
  typed reaches a run, `ctrl+w` is refused (a run wraps itself), and a watched batch's archives
  are byte-for-byte what a headless batch's would be — asserted by playing the same fixture
  both ways and diffing. `ctrl+x` still cancels the call in flight and the loop asks again;
  `ctrl+q` stops the batch, leaving the run in flight resumable via `bench run --resume`.

### Fixed
- **A session the frontend stopped is no longer archived as a turn-cap breach.** `bench run`
  read every non-wrapped ending as "hit the cap" and stamped a `cap` event for it — so a run
  ended early recorded a ceiling it never reached, and `--resume` skipped it as terminal. It is
  now `incomplete` and resumable.
- **`play --player auto --ui tui` no longer crashes on a typed line.** The scripted player has
  no inbox; typing at it now says so.

### Changed
- **Prompt trims across the agents.** `campaign-analyst`, `dm`, `log-extractor` and `player` lose
  prose that told an agent about orchestration it never acts on, and `session-flow`/`session-close`
  stop telling the runner that a between-session team will tidy up whatever it improvised — which
  priced improvisation at zero. No rule changed; the standing criterion is that an agent is told
  about machinery only where recognizing it changes its behavior.
- **A `bench run` narrates its reconcile.** The between-session pass is the longest stretch of a
  run and used to print one line before going quiet for minutes; it now reports each stage
  (`reconcile: handoff… digest… …`) as it starts. This falls out of routing bench through the
  same `Lifecycle` the TUI plays on, which also retires bench's private `Game`/player-session/
  reconciler wiring — the same objects, one construction.

### Added
- **Watch the scripted player in the TUI (`gm-llm play --player auto --ui tui`).** The last
  unbuilt cell of the play grid. An unattended run now renders in the full TUI — scene pane,
  behind-the-screen stream, gate verdicts, combat beats — with the turn cap (`--turn-cap`) and
  the character packet (`--character`, else a `*.player.md` at the project root) working as they
  do on the console. `ctrl+x` cancels whichever call is in flight and the loop re-asks; the
  session survives it. `ctrl+w` wraps a watched run once the turn in flight finishes.
- **`bench tokens` — what a run cost, retroactively.** opencode already aggregates
  `tokens_input/output/reasoning/cache_read/cache_write` and `cost` per session, keyed on the
  session's directory, and every bench run plays in its own dir — so a prefix match reports runs
  that were never instrumented for it, including ones already on disk. Per-agent split, grading
  (`grade-ws`) kept in its own column rather than folded into what play cost, and `--json`. Pass
  `--price-in/--price-out/--price-cache-read` for a hypothetical cost table; without them no
  dollar figures are shown, since the only cost opencode records on a free tier is `0.00`.
  Reasoning tokens are reported as a separate surcharge line because whether a provider bills
  them inside `output` or on top varies. The reader is read-only and fails soft — a missing store
  or a renamed column yields a reason string, never an exception into a benchmark run.
- **A benchmark score (`bench report`).** Dedup'd violations now roll up into a 0–100 *integrity
  score*: each violation costs penalty points by severity (trivial 0.25, minor 1, major 4,
  critical 12), the points normalize by graded units (turns + stage gates) into a rate, and the
  rate maps to the score (0 at 2 points/unit). Five dimension subscores — canon fidelity,
  information discipline, player agency, mechanical integrity, record integrity — share the same
  denominator, so the composite derives from the total penalty instead of averaging subscores,
  and the per-dimension deficits sum to the total deficit. Reported beside the severity vector,
  not in place of it. Rubric v1 now shows the grader the point table itself, so it grades knowing
  a rung is arithmetic and not a comment — with warnings against both inflating to `critical` and
  flattening everything to `major`. A test pins the rubric's table to the weights in code.

- **Resumable bench runs (`bench run --resume`).** A play that hits a sustained rate limit mid-session
  is now recorded `incomplete` (not `failed`) with its turns intact — the transcript and score archive
  stay on disk. `bench run --resume` picks every incomplete run in `--out` back up and continues it in
  place: it re-opens the run's own archive (append, no new file — the grader still reads one coherent
  turn stream), re-primes the runner from the transcript, continues turn ids past the break, skips a
  second `conditions` event, and updates the run's manifest line in place. Rate limits no longer burn
  progress on an overnight free-tier batch. (A give-up *before any turn lands* is still a real `failed`.)

- **`--resume` also finishes a reconcile the rate limits ate.** A stall in the post-wrap pass leaves a
  run that is genuinely `complete` as play — so a play-only sweep skipped it forever, while the grader
  read the stages that never ran as clean play rather than as missing data. `reconcile_pending` now
  asks the second, orthogonal question off the archive (the `propagation` stage event, reconcile's last
  gate, absent under a `reconcile: true` condition), and `--resume` picks those runs up too. Such a
  resume runs the post-wrap tail and nothing else: the turn loop never opens, so a wrapped session
  can't grow turns, and both halves of the tail are idempotent — handoff no-ops on existing notes, and
  the reconciler's stage markers restart it at the stage it died on, so it pays only for what's left.
  This is also the *only* correct repair route: `dev reconcile` mints a fresh archive per invocation,
  which would strand the recovered findings in a file `batch.jsonl` doesn't point at — the
  split-archive failure `unmanifested_archives` exists to catch.

- **The `conditions` event fingerprints the prompts.** A sha256 over every `.md` under the run's
  `.opencode/agent` + `.opencode/skills` and the package's `orchestrator/prompts` (relative path and
  content both in the digest, so a rename counts), read from the *run dir* — the copy that actually
  reached the model, not whatever the checkout says now. The prompts are the tier-0 subject, so two
  batches could previously share a condition signature while running materially different prose and
  get pooled and averaged; the hash joins `_identity`, so the mixed-conditions banner fires instead.
  Also makes "did this batch include change X?" answerable from the archive alone. Archives written
  before it carry no fingerprint, report as `prompts=unstamped`, and still pool with each other.

### Changed
- **One session loop, `orchestrator.play_session`.** The TUI, `dev autoplay` and `bench run`
  each carried their own turn loop; there is now one, and the axis between them is a
  `PlayerSource` — `KeyboardPlayer` (a frontend hands lines in) or `AgentPlayer` (the scripted
  `player` agent, character packet and story-so-far included). Rendering is a set of hooks.
  Three knock-on fixes fall out of the unification: a session **resumed into a live fight** now
  fights instead of sending a normal turn into a live tracker (autoplay and bench both got this
  wrong), console autoplay's turn cap now covers **combat slots** as bench's already did, and a
  cancelled turn no longer burns a turn against the cap.
- **One agent-driven fight loop, `orchestrator.play_combat`.** `gm-llm dev autoplay` and
  `bench run` had near-duplicate combat drivers that differed in turn accounting; they now share
  one, with bench's "each PC slot burns a turn against the cap" as the implementation and
  `turn_cap=None` as the human frontend's explicit opt-out.
- **`dev/cli.py`, `dev/ping.sh`, and `gm_llm/tui/__main__.py` are gone.** Their commands moved
  into the unified CLI: `dev/cli.py play` → `gm-llm dev autoplay` (and `--turns` → `--turn-cap`,
  matching `bench run`), `dev/cli.py tui [--setup]` → `gm-llm play --mock [--setup]`, `status` and
  the new `tokens` promoted to the top level, `prep`/`reconcile`/`lint`/`ping` into the `dev`
  group. `ping` is now Python, so the CLI has no shell dependency.
- **`reconcile` is dev-only, deliberately.** The lifecycle already decides from disk whether a
  campaign should be playing or reconciling, and the TUI drives the post-session pipeline itself.
  Running it by hand applies a non-idempotent canon pass plus two commits *outside* that state
  machine — a repair tool, not a recovery button, so it doesn't sit on the player surface.
- **Grading counts violations, not verdicts.** A checker report enumerating several distinct
  problems on one turn used to grade as a single finding; it now splits on the report's numbered
  list and grades each separately (refs gain a `#n` suffix). On the first scored run that turns
  9 findings into 15. An unnumbered or single-item report is unchanged.

- **Bench turn cap default 30 → 50.** The fixture's sessions were wrapping right at 30 (session 3's
  transcript is the campaign's largest), leaving no headroom — a session a turn longer would trip the
  cap and skip reconcile. 50 gives a natural wrap room to land before the safety net.

- **Stall watchdog widened for heavy calls; default given headroom.** The per-call stall budget (abort
  a call with no stream activity for this long) rises from 120s to 180s, and reconcile/handoff — which
  read whole transcripts (their prefill emits no stream parts, so a working first token is minutes out)
  — now run under a 900s budget (`Backend.patient()`), half reconcile's ~30-min hard `turn_timeout`.
  Tool-call parts count as activity, so only a genuine silent gap trips it. Those heavy calls also
  drop from 4 retries to 2: mimo-free throttling is a *silent hang*, so a throttled heavy call burns
  the full 900s budget every attempt with nothing to show — 4× would dead-wait ~an hour, where 2 still
  covers one genuinely-slow legit call, then gives up in ~30 min and lets a resume pick it up when the
  caps clear. The give-up message no longer asserts "rate-limited hang" (it can't tell a rate limit
  from a slow first token).

- **Checker false-positive narrowing.** `check-conduct`'s player-agency check no longer flags an NPC
  deflecting or partly answering a question, the DM correcting a player's mistaken description of a
  world fact, or un-echoed player dialogue/action — only a wholly-unacknowledged action, or narration
  that *contradicts* what the player declared. `check-turn` now distinguishes a draft *extending* the
  transcript with consistent detail (ordinary play) from *conflicting* with it (the real error).

- **Checker feedback is suppress-only.** `check-conduct` no longer treats
  `campaign/feedback/session-run.md` as a binding rule set — feedback can now only *excuse* a flag it
  would otherwise raise, never create a new one. Stops soft runner-craft guidance ("offer X when
  adrift") from silently becoming a hard checker gate, and keeps the benchmark's measurement
  instrument from drifting as player feedback accumulates.

### Fixed
- **Quitting the TUI can no longer hang the process.** The play worker runs on a thread and
  waits on the app's event loop to render; on the way out Textual cancels the worker's coroutine
  while its thread keeps running, so a thread parked on the player (or on combat's confirm gate)
  kept the interpreter's thread pool from joining at exit. Everything the worker can park on is
  now released on unmount, and a hook that fires after the app has stopped is a no-op.

- **The turn cap is no longer treated as a condition.** A cap no run reached is inert — it reaches
  no prompt (it lives entirely as a loop bound in `bench/runner.py`) and the wrap nudge keys off
  opencode's context threshold, not the cap — so runs configured at 30 and at 50 pooled fine but
  were flagged `MIXED CONDITIONS` and refused. Comparability now ignores the configured cap and
  flags what actually matters: a run the cap *bound*, which is truncated, skipped reconcile, and
  has no stage findings. The report banners those under instrument health.

- **An archive the manifest doesn't point at can no longer vanish from the score.** `bench grade`
  and `bench report` read `batch.jsonl` and nothing else, so a stray archive in a run dir
  contributed no violations — scoring as clean play rather than as missing data. Both now scan the
  run dirs and name any unmanifested archive loudly (the report banners it under instrument
  health); `--resume` likewise warns instead of silently taking the newest when a run dir holds
  more than one. Deliberate backup dirs are excluded. This is the split-archive incident, where
  reconcile invoked as its own `bench run` wrote a second stream whose stage findings would have
  been dropped without a word.

- **Two checks flagging one draft are no longer double-counted.** The grader's dedup window
  excluded same-turn findings entirely, so when `check-turn` and `check-conduct` both caught the
  same mistake — the commonest double-count there is — the second was structurally unable to be
  marked a duplicate. The window now spans the same turn, while siblings enumerated by the *same*
  check stay out of it (those are distinct by construction). Rubric v1 gained the matching
  guidance, plus a note that the check which flagged a violation constrains its category —
  `record-integrity` covers the between-session record gates only.

- **A naturally-wrapped bench run is no longer demoted by a post-wrap stall.** Handoff and reconcile
  run *after* the session wraps; a rate limit (or a slow large-input call the retries gave up on) there
  used to propagate out and relabel the fully-played run `incomplete`/`failed` with a stale turn count
  — while its archive still read `complete`, so `bench run --resume` (which classifies from the archive)
  skipped it forever, stranding the contradiction. Play is the measured subject: once it wraps the run
  is `complete`, and a failed post-wrap step just leaves reconcile undone.

## [0.4.2] — 2026-07-18

### Changed
- **Post-wrap start gate** — after a session wraps (reconcile + prep the next), the TUI now stops
  and asks `Session N+1 planned — start playing it now?` instead of auto-opening the next scene.
  Answering N leaves N+1 prepped and unopened (start it later with ctrl+w or the esc menu), so you
  can inspect the plan — or stop — before the opening turn is drafted, rather than having to wipe
  an auto-generated first turn. Mirrors the existing setup→play and wrap-pending transition gates.

## [0.4.1] — 2026-07-17

Combat wired into every interface (the C0–C5 engine finally has a driver), autoplayer hardening,
and session-end recovery — dev tooling and fixes; combat still awaits its live shakedown.

### Added
- **Per-turn player reminder** — the autoplayer now gets a fresh `player-reminder` brief in front
  of every DM beat (the beat fenced in `<dm>…</dm>`), mirroring the runner's `turn-reminder`: a
  per-turn algorithm (roll handling, one action, no recap/repetition, attempt-never-resolve, no
  invented facts). One home (`orchestrator/prompts/player-reminder.md` + `prompts.player_turn`),
  used by both `dev/cli.py play` and the bench runner. Counters the observed long-session drift:
  echo spirals, world-narration, and perception loops.
- **Combat driver** — `CombatDriver` (in `orchestrator/combat.py`): the combat *sequencing
  policy* in the library, once. It pumps the initiative loop (NPC beats confirmed each; stops at
  the PC's slot or the fight's end), threads interjections (a PC reaction returned from its
  `on_beat` render hook → rollback + replay + re-present) and cancels, and drives a resume
  straight into a live fight. All three interfaces now enter combat on `start_encounter` and stay
  mechanical (render a beat, get input, call the next method): the **TUI** (an initiative mode
  that streams NPC beats, solicits the PC's slot, and takes Enter-to-confirm / type-to-interject),
  **`dev/cli.py play`**, and the **bench runner** (each PC slot counts as one turn against the cap,
  so a fight can't make a run uncappable). Fixes the C0–C5 gap where a live `start_encounter`
  degraded to free-prose combat in every interface. The offline `MockGame`/`MockLifecycle` gained
  a scripted combat episode so the TUI demos a fight without a backend.
- **Player combat brief** — `player-combat-reminder` + `prompts.player_combat_turn`, the combat
  mirror of `player-reminder`/`player_turn`: declare ONE slot action with its target and any
  movement, roll only when asked (report the total, nothing else), deferring to the normal turn's
  hard rules. Used by the autoplay loops on a PC combat slot.
- **Session-end recovery** — a conservative close-marker nudge in `loop.py`: when a non-opening
  draft ends the session in *prose* (a bare "session complete / ends here" trailer) but never
  calls `task_complete`, the orchestrator sends ONE bounded follow-up asking for the call. If it
  lands, the turn is `session_complete`; if not, play continues unchanged (the match is tight
  enough never to fire on ordinary narration). The recovery is recorded on the archive turn event
  (`close_nudged`). `turn-reminder` step 5 now states outright that a session ends only via
  `task_complete`, not narration. Fixes a live failure where the runner wrote `--- *Session
  complete.*` three times and the session never closed.
- Tests: `dev/test_combat_driver.py` (pump, PC slot, interject, cancel, resume), combat-episode
  cases in `dev/test_bench.py` (enter/exit combat, turn-cap math), and close-nudge cases in
  `dev/test_archive.py`.

### Changed
- `dev/cli.py play` needs no hand-holding: it auto-resumes an in-progress session (`--fresh` is
  now the only way to overwrite a transcript), auto-discovers a `*.player.md` packet at the
  project root, stops when the runner ends the session (capturing the handoff notes and pointing
  at reconcile), refuses to play a session already marked complete, and treats `--turns`
  (default 30, up from 6) as a cap rather than a fixed count.
- Golden prompt stream (`dev/golden/stream.jsonl`) re-recorded for the `turn-reminder` step-5
  clause; the only byte change vs. the prior recording is that clause.

## [0.4.0] — 2026-07-17

Benchmark harness — gm-llm doubles as a tiered scaffolding benchmark (design in `BENCHMARK.md`):
fixture runner, grader, report, and golden-stream regression armor (B1/B2/B4).

### Added
- `CHANGELOG.md` (this file).
- **Benchmark runner (B1)** — `bench run` (dev-only, under `gm_llm/bench/`, wheel-excluded like
  `dev/`): plays a frozen fixture campaign through the product's gated loop N times and leaves one
  condition-stamped score archive per run. Each run assembles a throwaway project (template +
  fixture `campaign/` + fresh git repo), emits a `conditions` archive event (fixture id/frozen,
  tier, turn cap, reconcile flag, per-agent model+temperature) ahead of play, runs to a natural
  `task_complete` close or a hard turn cap (cap breaches stamped and skipped past reconcile), and
  records outcomes to `<out>/batch.jsonl`. Batches are rate-limit-resilient (a failed run is
  recorded and the batch continues) and resumable (re-invoking the same `--out` appends).
- **Provisional fixture** `dev/fixtures/hollowfell/` — a frozen `init + session-1 plan` campaign
  (world, canon, the `dallid` PC) with a `fixture.json` condition stamp. Marked provisional: it is
  re-frozen from steady-state canon before the B3 baseline.
- `dev/test_bench.py` — standalone checks for run-dir assembly, the conditions event, natural close,
  cap breach, and batch resilience (all over fakes; no network/npm/opencode).
- **Benchmark grader + report (B2)** — `bench grade` and `bench report` (dev-only, under
  `gm_llm/bench/`). `bench grade` scores every violation the in-loop checker flagged in a batch's
  archives: it assembles a minimal throwaway grading workspace (`<out>/grade-ws/` — the pinned
  `grader` agent + a bench-only `submit_grade` plugin), boots one backend over it, and grades each
  finding in its own session against the versioned severity/category rubric (`rubric-v1.md`,
  embedded verbatim in each brief). Grades are delivered as structured `submit_grade` tool calls —
  never parsed from prose; a grader that won't call the tool after one nudge is recorded `ungraded`.
  Output is `grades-<run_id>-v1.jsonl` beside each archive (header + one line per finding: severity,
  category, rationale, `duplicate_of`), idempotent per rubric+model unless `--force`. `--model`
  overrides the pinned grader for a V2 re-grade (grades are derived data); a short window of
  already-graded findings rides in each brief so a violation persisting across consecutive turns is
  marked `duplicate_of` and doesn't multiply the score; `--double [--sample N]` re-grades a sample in
  independent sessions and reports severity/category agreement. `bench report` (no model calls)
  aggregates archives + grades into a per-run and per-batch summary — violation counts by severity
  (raw + dedup'd), correction rate, the prominent defaulted-verdict rate, ungraded count,
  turns-to-wrap, session-close outcomes, stage gates, context growth — as distributions
  (min/median/max), and flags a batch that mixes conditions loudly at the top. `--json` for machine
  output. Grader assets live under `gm_llm/bench/assets/` (instrument, not product — never shipped in
  the wheel).
- `dev/test_grade.py` — standalone checks for brief construction, finding extraction, the grades-file
  shape + idempotence, the ungraded-after-nudge path, dedup via `duplicate_of`, `--double` agreement
  math, and report aggregation incl. the mixed-conditions warning (all over a fake grader backend;
  no network/npm/opencode).
- **Golden prompt-stream test (B4)** — `dev/test_golden_stream.py` + `dev/golden/stream.jsonl`:
  records the exact model-facing prompt stream (one `{seq, agent, kind, message}` record per
  backend call) the orchestrator emits for a scripted setup → session-1 prep → play → handoff →
  reconcile pass, and diffs future streams against it byte-for-byte. Drives the real
  Setup/Planner/Game/Reconciler + real Gate + real CanonPreloader over a synthetic on-disk campaign
  and a scripted-by-agent fake backend (so the checker-bound briefs — canon excerpts, correction
  passes, `task_complete`/`report_findings` handling — are all in the recorded surface). Free
  regression armor for the B5 playbook refactor. `UPDATE_GOLDEN=1 python dev/test_golden_stream.py`
  re-records.

### Changed
- Version is single-sourced from `gm_llm/__init__.py` `__version__`; `pyproject.toml` reads it
  dynamically, so the CLI, `gm-llm update`, and package metadata can no longer drift.

## [0.3.0] — 2026-07-17

Combat play mode — a full tracker-backed combat system (design in `COMBAT.md`).

### Added
- **Combat tracker** — a file-backed opencode plugin over a pure engine: HP, egocentric positions
  (world-Cartesian storage, Chebyshev projection), the bounded condition library, initiative, the
  one-reaction economy, the `dead` bit + death saves, and the turn-slot timer/obligation channel.
  Holds `committed`/`pending` frames with forward mutators + `rollback`.
- **Initiative-driven mode switch** — the orchestrator drives combat turn by turn with granular
  commit / confirm / interject, plus resume-mid-combat recovery (rollback + re-resolve).
- **`check-combat`** — a narrative-checker role validating the `committed → pending` mechanical delta.
- **Repertoire ledger** — the PC's `{slug}.repertoire.md`, a third ledger of reaction triggers with a
  player-owned `Stop:` toggle, seeded at create/level-up and grown from play.
- **Planning layer** — a stat-block template, a `world/bestiary/` reusable-creature file kind
  (registered in a new INDEX `Bestiary` table), and the `combat-balance` skill (solo-game difficulty
  by feel).
- **Play-craft** — the `combat-run` skill and the `combat-reminder` per-turn brief.
- **AoE queries** — `burst` (sphere / cylinder / cube), `cone`, and `line` shape reads; the model
  places the aim egocentrically and the tracker computes the catch (no coordinates surfaced).
- **`/refine-prompts`** skill and prompt-writing conventions in `CLAUDE.md`.

### Changed
- Prompt refinements across agents and skills (dedup, tightened scope, SRD-safe combat examples).

## [0.2.0] — 2026-07-14

### Added
- Fenced control channels (`<turn-reminder>` / `<correction>` / `<prepared-context>`), the deterministic
  session-wrap nudge with a TUI context-usage readout, and session-completion tracked as a disk fact.

### Changed
- Disabled opencode auto-compaction in favor of the deterministic wrap; documented context management
  in `SPEC.md` / `README.md`.

## [0.1.1] — 2026-07-05

### Fixed
- Windows: force UTF-8 on stdio and subprocess text pipes.

## [0.1.0] — 2026-06-24

### Added
- Initial release: the D&D campaign-management framework over opencode — setup → play → reconcile
  orchestrator, agents, skills, and the TUI.
