# CLAUDE.md — gm-llm

gm-llm is an opencode-driven D&D game-master system: the orchestrator (`gm_llm/orchestrator/`)
drives headless `opencode serve` agents through setup → play → reconcile. Background reading:
`SPEC.md` (what it is), `PLAN.md` (packaging/Windows), `BENCHMARK.md` (the benchmark workstream and
its design principles).

## The prompts

Model-facing prose lives in three places:

- `gm_llm/assets/opencode/agent/*.md` — the agents (dm, dm-runner, narrative-checker, …).
- `gm_llm/assets/opencode/skills/*/SKILL.md` — loadable craft (session-run, social-play, the
  `check-*` gates, planning/setup/reconcile skills).
- `gm_llm/orchestrator/prompts/*.md` — orchestrator-injected briefs (e.g. `turn-reminder`, prepended
  to every player message).

These prompts **are** the product (the benchmark's `low` tier). The target model is modest (mimo) —
write for it.

## Writing prompts

- **Concise and precise beats verbose.** Every line spends the model's attention. State a rule once,
  well.
- **One canonical home per rule.** Elsewhere, point to it — never restate. (session-run owns the
  delivery carve-out; social-play and dm-runner point at it.)
- **Modularize around loading.** `session-run` is the always-loaded core — keep it to *universal
  per-turn rules*. Scene-specific craft lives in companion skills (`social-play`, `discoveries`,
  `session-flow`) loaded on demand. Only move a rule into a companion if it is inherently tied to the
  scene that loads it; a universal rule parked in an unloaded skill is silently absent.
- **Explicit handoffs, never silent gaps.** Where the core omits detail for modularity, say "load X
  and follow it" and name what X owns. The `turn-reminder` and session-run both drive loading ("load
  the scene's skill before you play it").
- **Don't re-enumerate steps a loaded skill owns** — that duplication drifts. Rule of thumb: drop
  enumerations owned by a loaded skill; keep terse ones sourced from orchestrator code or the agent's
  own identity.
- **Most lines are scar tissue** — added to fix a specific model failure. Before cutting, read the git
  history (the `/refine-prompts` skill automates this). Preserve the constraint; tighten the words.
  Keep concrete failure-mode cues and examples.
- **Examples teach — keep them correct.** A wrong rules example (e.g. conflating spell level with
  character level) teaches the model the wrong rule.
- **Don't recompose or template tier-0 prose** (BENCHMARK.md principle 1): the interwoven
  contract-and-craft texture is tuned as-is — trim in place.

## Operational

- Prose changes should ideally be verified against a score baseline; none is banked yet (BENCHMARK.md
  B3), so lean on the git-archaeology discipline in the meantime.
- Changes reach a live campaign via `pipx reinstall` (package code + assets) + `gm-llm update` in the
  campaign (copies skills into its `.opencode/`). **Never while a TUI session is live** — quit at the
  wrap prompt first.
- To refine prompts as bloat builds up, use the **`/refine-prompts`** skill (the git-archaeology
  method).

Commit style follows the global rule (short, descriptive, no attribution trailer; commit only when
asked).
