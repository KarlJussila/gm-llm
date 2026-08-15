# CLAUDE.md — gm-llm

gm-llm is an opencode-driven D&D game-master system. The shipped Tier-0 profile drives MiMo through
setup → play → reconcile; the active product direction is a clean Tier-1 profile for Luna at
`xhigh` reasoning. Both use the code-owned campaign/runtime substrate in `gm_llm/orchestrator/`.

This file holds the **stable** facts worth loading every session. Anything that changes
round-to-round lives in `HANDOFF.md`, not here.

## Documentation routing

| File | Purpose | Cadence |
|---|---|---|
| `CLAUDE.md` (this file) | Stable orientation, routing, standing rules, the gate | Rarely — only when a *durable* fact changes |
| `HANDOFF.md` | **Current state only**: live numbers, the next task, where things stand | Rewritten after **every** round |
| `ROADMAP.md` | All remaining work, sequenced, with an effort level per task | When sequencing changes |
| `design/findings.md` | Append-only **per-round record** (Parts 1–N); the reasoning archive | One Part per round |
| `design/open-questions.md` | The live backlog of **unresolved** decisions and gaps | As items open; **delete** when resolved |
| `README.md` | The user-facing manual: install, quick start, the TUI and CLI | When user-facing behavior changes |
| `design/README.md` | **What the system is** — the routing table for `design/`, plus the architecture, the runtime seams, and the constraints/non-goals | When the design changes |
| Plan-of-record docs | `design/benchmark.md`, `design/combat.md`, `design/frontends.md` — one per workstream, linked from `design/README.md` | When that workstream's design changes |
| `dev/MAINTAINING.md` | Dev-side conventions: what an update delivers, the Windows portability rules | When the dev-side process changes |

### Keeping the docs clean

- **One fact, one home.** Don't copy; point. A restated rule is a rule that will rot — this
  repo has already lost `dev/MAINTAINING.md`'s versioning section that way.
- **HANDOFF.md is current-state only, never a changelog.** "The prior round did X" belongs in
  a Part. It has a hard line budget the lint enforces.
- **Never type a count into prose.** Numbers live in a ratchet, in HANDOFF's generated block
  (`tools/status.py`), or nowhere. HANDOFF is rewritten each round, and a session rewriting a
  doc carries numbers forward from context instead of re-deriving them.
- **Resolved open-questions are deleted, not tombstoned.**
- **Park deferrals on a ROADMAP track, never on a round.** A round closes; a track persists.
- **After every round:** append the Part, rewrite `HANDOFF.md`, update whatever doc the round
  changed. Use `/close-round`.

## Standing rules

- **Rounds:** one ROADMAP task per session. The effort level is in `HANDOFF.md` § Next task;
  closing the round includes rewriting that block. A round that lands code but doesn't close
  the docs — or doesn't commit — has not been handed off.
- **Source of truth:** where a doc and the code disagree, **the code wins and the doc gets
  fixed in that round** — not filed as a question.
- **Git:** short, plain, descriptive messages; no attribution trailers. Commit only when asked —
  **except when closing a round, which always commits without asking.** If something needs
  Karl's decision, raise it and *don't* close the round; close it once that's settled.
  `/close-round` § 6 owns the detail.

## How to run things

### The gate — every one of these green, every round

```sh
python -m compileall gm_llm                        # syntax across the package
for t in dev/test_*.py; do python "$t" || break; done   # the suite
python3 tools/status.py --check                    # HANDOFF's numbers are current
python3 tools/lint_docs.py                         # planning docs agree with the repo
```

**The suite is not pytest.** `dev/test_*.py` are standalone scripts with a homegrown `tmp`
helper — running them under `pytest` produces a wall of `fixture 'tmp' not found` collection
errors that look like breakage and are not. Run each as a script. (`lint_docs.py` check 8
fails any doc that says otherwise.)

**A red suite is this round's problem even if this round didn't break it.**

## The prompts

Model-facing prose lives in three places:

- `gm_llm/assets/opencode/agent/*.md` — the agents (dm, dm-runner, narrative-checker, …).
- `gm_llm/assets/opencode/skills/*/SKILL.md` — loadable craft (session-run, social-play, the
  `check-*` gates, planning/setup/reconcile skills).
- `gm_llm/orchestrator/prompts/*.md` — orchestrator-injected briefs (e.g. `turn-reminder`, prepended
  to every player message).

These prompts **are** the shipped Tier-0 MiMo product. They are now a frozen legacy profile, kept
playable and protected by the golden prompt stream. The Luna Tier-1 surface is authored separately;
do not use Tier 0 as its prompt template. See `design/luna.md`.

## Writing prompts

The rules below describe maintenance of Tier 0. Tier-1 prompt work begins from Luna's observed
behavior and `design/luna.md`: no Tier-0 guard, reminder, skill choreography, or role split carries
over without a reproduced need.

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
- **Don't recompose or template tier-0 prose** (`design/benchmark.md` principle 1): the interwoven
  contract-and-craft texture is tuned as-is — trim in place.

## Operational

- Tier-0 prose is frozen except for a supported-path regression. Luna prose is verified first by
  the diagnostic slice, then by profile-stamped benchmark runs; model and reasoning level are both
  part of the condition.
- Changes reach a live campaign via `pipx reinstall` (package code + assets) + `gm-llm update` in the
  campaign (copies skills into its `.opencode/`). **Never while a TUI session is live** — quit at the
  wrap prompt first.
- To refine prompts as bloat builds up, use the **`/refine-prompts`** skill (the git-archaeology
  method).

## Versioning & releases

Pre-1.0, but keep the minor/patch line meaningful:

- **Minor** (`0.N.0`) — a user-facing feature set or a new mode (combat was `0.3.0`).
- **Patch** (`0.N.M`) — a fix, a prose/prompt tweak, small infra.

Rules:

- **Single source of truth: `__version__` in `gm_llm/__init__.py`.** Bump it *there and nowhere else* —
  `pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic]`), and `gm-llm --version` /
  `gm-llm update` report it, so they can't drift. (Validate a version change resolves with
  `python -m build --sdist` if you touch the build config.)
- **Keep `CHANGELOG.md` in step** (Keep a Changelog format). Add notes under `[Unreleased]` *as you
  go*; on a bump, rename `[Unreleased]` → `[x.y.z] — YYYY-MM-DD` and open a fresh `[Unreleased]`.
- **Bump when the feature set lands, not in a big-bang later.** A whole play mode once accumulated
  across ~29 commits on one version before anyone noticed — that's the anti-pattern. If a change is
  worth a CHANGELOG line, it's heading toward a bump; flag it.
- **"Release" here = the bump commit** (there's no PyPI publish): campaigns pick it up via the
  `pipx reinstall` + `gm-llm update` flow above. Make the bump its own commit, then **tag it with an
  annotated tag**: `git tag -a vX.Y.Z -m "<headline>"`. `git describe` then reads e.g.
  `v0.3.0-2-g<sha>` so any checkout says which release it's built on.

Commit style follows the global rule (short, descriptive, no attribution trailer; commit only when
asked).
