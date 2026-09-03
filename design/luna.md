# Luna Tier 1 — a clean product path

Plan of record for the Luna-targeted Tier-1 product. The benchmark that measures it is
[benchmark.md](benchmark.md); the shipped MiMo path remains the Tier-0 reference.

## Outcome

Tier 1 is a first-class gm-llm experience built for `opencode/gpt-5.6-luna` at `xhigh` reasoning.
Luna supports `high`, `xhigh`, and `max`; `xhigh` is the deliberate quality-first starting point
between the latter two, based on observed improvement at higher reasoning levels. It should let Luna
carry the judgment it is good at instead of making it enact control machinery built around
MiMo's failures. Tier 0 remains installed and playable as the deliberately over-scaffolded MiMo
experience; it is not the template from which Tier 1 is derived.

"Start from scratch" applies to the model-facing system: agent roles, prompt prose, skill use,
context delivery, gate feedback, and setup/play/reconcile decomposition are all open to a simpler
answer. It does not discard code-owned capabilities whose value is independent of the model:

- the campaign's human-readable files and player-knowledge boundary;
- deterministic dice and combat bookkeeping;
- transcript capture, completion markers, checkpoints, and git ownership;
- the backend, lifecycle/frontends, cancellation, and process management; and
- the raw benchmark archive and offline grading path.

Those are substrate. A Tier-0 behavior is not substrate merely because the orchestrator currently
implements it.

## Design rules

1. **Observe Luna before designing for Luna.** The first artifact is a run, not a framework. Give
   Luna the session plan, the relevant campaign contract, and the deterministic tools with a small
   role prompt. Record where it succeeds, what it reads or calls, and where it actually needs help.
2. **One concrete second path before an abstraction.** Add only the seams the first Tier-1 vertical
   slice needs. Once Tier 0 and Tier 1 both exist, common mechanics may be extracted from evidence;
   do not first turn Tier 0's hard-coded sequence into a generic playbook and call that neutrality.
3. **No inherited scar tissue without a reproduced failure.** Per-turn todo lists, forced skill
   reloads, staleness nags, mandatory micro-stages, and checker-fed correction are absent by
   default. Each enters Tier 1 only if a Luna run demonstrates the failure it repairs.
4. **The checker is an instrument, not a copilot.** Tier-1 drafts may be observed and archived by
   the same checks so runs remain measurable, but a MiMo verdict is not fed back into Luna unless
   an experiment shows that correction improves the game. Instrument failure must not steer the
   subject.
5. **Profiles own model-facing behavior.** A campaign chooses a product profile; the profile pins
   its intended model, reasoning level, and complete model-facing assets. The install owns the
   shipped profile definitions. Model and reasoning are both part of a run's condition identity;
   avoid a matrix of per-agent campaign settings until a real use case needs one.
6. **Preserve public outcomes, not internal topology.** Setup must leave a playable campaign, play
   must leave a transcript and clean completion fact, and reconcile must fold play into canon.
   Tier 1 need not preserve Tier 0's two-primary-agent split or its exact stage graph to deliver
   those outcomes.

## The first slice (probed in Part 11)

The discovery probe ran against the Hollowfell session-3 fixture using `openai/gpt-5.6-luna-fast` at
`xhigh` reasoning (`variant: xhigh`) with observe-only checking. The run wrapped naturally via
`task_complete` in 13 player turns (3532s) without per-turn reminders, todo choreography, forced
skill loading, or correction delivery.

### Evidence-backed live-play contract

1. **What Luna needs once (at session start):**
   - **Prepared context:** the prepared session plan plus baseline canon and named entities
     (`runner_preload()`), delivered once in front of the opening kickoff.
   - **Role & spoiler boundary:** concise DM authority over narration, NPC dialogue, and 5e rules
     adjudication, with an absolute boundary on unearned secrets and plot spoilers.
   - **Conduct craft stated in the profile prompt:** standing craft rules (e.g. withholding DCs, closing
     exploratory scenes on situations rather than multiple-choice menus) are followed when stated in the
     prompt; they do not require separate loadable skills or in-flight correction.
   - **Campaign filesystem orientation:** directory layout (`world/`, `characters/`, `sessions/`) and
     file tools (`read`, `glob`, `grep`, `list`).
   - **Deterministic tool contract:** `dice` for rolls, combat tracker tools if initiative triggers,
     and `task_complete` with handoff `notes` to wrap.

2. **What Luna retrieves on demand:**
   - Context lookups are targeted and autonomous. When Luna needed to verify communication links between
     Dallid, Wren, and the Concordance on turn 13, it autonomously called `glob` and `read` on
     `campaign/sessions/session-1-notes.md` without being reminded or prompted to do so.
   - Universal per-turn skill re-loading is unnecessary; Luna retains instructions and context across
     the session.

3. **Which code boundaries remain:**
   - Deterministic dice and combat state tracker (`plugin/combat-tracker.ts`).
   - Transcript recording (`session-{N}-transcript.md`).
   - Session completion handling: the orchestrator must extract `notes` from `task_complete`, and
     safely handle final narration if passed in the tool's `player_message` argument.
   - Observe-only instrumentation (`check-turn`, `check-conduct`, raw archive JSONL).

4. **Which Tier-0 mechanisms stay absent:**
   - **No per-turn reminder brief:** Luna tracks narrative context and rules across turns without a
     changing orchestrator brief prepended to player messages.
   - **No todo choreography:** `todowrite` is omitted; Luna structures multi-step actions cleanly
     within its own reasoning space.
   - **No staleness nags:** lookup tracking and escalating reminder lines are retired.
   - **No wrap countdown banners:** Luna recognizes the plan's closing beat and initiates wrap on its own.
   - **No in-loop correction:** the checker observes and archives verdicts without perturbing or
     re-prompting the live DM.

## Product shape

Tier 1 grows outward from that slice in outcome-sized steps:

- **Live play:** a dedicated Luna asset surface and a public profile selection reach the existing
  play UI while bypassing Tier-0 control behavior.
- **Campaign work:** setup and reconcile are re-authored against their output contracts. Start
  with the largest coherent Luna task and split only where observed quality or recovery demands it.
- **Operational fit:** resume, cancellation, combat, context pressure, update, and campaign
  migration work through the Tier-1 path.
- **Measurement:** the benchmark stamps the profile and complete model-facing identity, observes
  checks without perturbing play, and banks a Luna distribution only after the path is viable.
- **Promotion:** Tier 1 becomes the recommended new-campaign experience only after an end-to-end
  campaign shakedown. Tier 0 remains selectable for MiMo and for the scaffolding comparison.

## Tier-0 preservation boundary

Tier 0 is frozen at its current behavior, including the partially landed reminder/staleness
experiment. The golden prompt stream protects it while shared substrate changes. Tier-0 work is
limited to regressions that break a supported user path, provider/API drift, and small changes
needed to keep it fun and runnable. Its unfinished prompt recalibration is not a prerequisite for
Tier 1, and a MiMo score baseline does not gate Luna work.
