# CLAUDE.md — gm-llm

gm-llm is an opencode-driven D&D game-master system: a Python orchestrator (`gm_llm/orchestrator/`)
drives model agents through campaign setup → live play → post-session reconcile, over a campaign
kept as human-readable markdown files.

It is being rebuilt for **GPT-6 Luna** (`openai/gpt-6-luna`, `xhigh` reasoning). The MiMo product
is retired — v0.5.0 is its last release. The model-facing prompts were rewritten for Luna at the
`luna-clean-slate` tag; what's left is testing and refining them. `design/luna.md` is the target;
`ROADMAP.md` is the order.

## Where things live

| File | What it is |
|---|---|
| `README.md` | The user manual: install, quick start, the TUI and CLI |
| `ROADMAP.md` | What's left, in order, per track — plus the open questions |
| `CHANGELOG.md` | Release notes (Keep a Changelog) |
| `design/README.md` | What the system is, and the map of `design/` |
| `design/luna.md` | The rebuild's design: principles, agents, layout, every workflow |
| `design/benchmark.md` | The benchmark: tiers, the pipeline, the stages |
| `design/combat.md`, `design/frontends.md` | Combat, and the engine protocol frontends speak |
| `design/findings.md` | Frozen history (Parts 1–11) — *why* earlier calls were made |
| `dev/MAINTAINING.md` | Dev-side conventions: what an update delivers, Windows portability |

**Docs rules:**

- **One fact, one home.** Point, don't copy — a restated rule is a rule that will rot.
- **The code wins.** Where a doc and the code disagree, fix the doc in the same change.
- **ROADMAP holds no history.** A landed task is deleted; git log is the record.

## How to run things

Use the project venv (`python3 -m venv .venv && .venv/bin/pip install -e .` if it's missing):

```sh
.venv/bin/python -m compileall gm_llm                             # syntax across the package
for t in dev/test_*.py; do .venv/bin/python "$t" || break; done   # the suite
```

**The suite is not pytest.** `dev/test_*.py` are standalone scripts with a homegrown `tmp` helper —
under `pytest` they produce `fixture 'tmp' not found` collection errors that look like breakage and
are not. Run each as a script. A red suite gets fixed before anything else lands.

## The prompts

Model-facing prose lives in three places:

- `gm_llm/assets/opencode/agent/*.md` — the agents.
- `gm_llm/assets/opencode/skills/*/SKILL.md` — skills the agents load on demand.
- `gm_llm/orchestrator/prompts/*.md` — briefs the orchestrator sends.

**Writing prompts for Luna** — the design rules are `design/luna.md` § Principles. On top of those:

- **Concise and precise.** Every line spends the model's attention; state a rule once, well.
- **One home per rule.** Elsewhere, point to it.
- **A skill's description says when to load it** — one line, never a summary of the contents.
- **Examples teach, so keep them correct.** A wrong rules example teaches the wrong rule.
- **MiMo's scar tissue doesn't carry over.** A guard, reminder or step from the old prompts comes
  back only when a Luna run shows the failure it repairs.
- **After the clean slate, guardrails are protected.** Prose added after the `luna-clean-slate` tag
  is trimmed only through the `/refine-prompts` process, and a commit adding a guardrail names the
  failure it fixes and the run that showed it — the campaign directory and the archive's run id
  (`.opencode/logs/archive-<run id>.jsonl`); a campaign or world name alone doesn't pin a run.

## Operational

- Changes reach a live campaign via `pipx reinstall gm-llm` (package code + assets) + `gm-llm update`
  in the campaign (copies skills into its `.opencode/`). **Never while gm-llm is running.** The best moment
  is when a session has ended and the TUI asks whether to wrap it up: `/quit` there, update, and the
  next `gm-llm play` asks again, so the wrap runs on the new code.

## Git

Short, plain, descriptive commit messages; no attribution trailers.

## Versioning & releases

Pre-1.0, but keep the minor/patch line meaningful:

- **Minor** (`0.N.0`) — a user-facing feature set or a new mode (combat was `0.3.0`).
- **Patch** (`0.N.M`) — a fix, a prose/prompt tweak, small infra.

Rules:

- **Single source of truth: `__version__` in `gm_llm/__init__.py`.** Bump it *there and nowhere else* —
  `pyproject.toml` reads it dynamically (`[tool.hatch.version]`), and `gm-llm --version` /
  `gm-llm update` report it, so they can't drift. (Validate a version change resolves with
  `python -m build --sdist` if you touch the build config.)
- **Keep `CHANGELOG.md` in step.** Add notes under `[Unreleased]` *as you go*; on a bump, rename
  `[Unreleased]` → `[x.y.z] — YYYY-MM-DD` and open a fresh `[Unreleased]`.
- **Bump when the feature set lands, not in a big-bang later.** A whole play mode once accumulated
  across ~29 commits on one version before anyone noticed. If a change is worth a CHANGELOG line,
  it's heading toward a bump; flag it.
- **"Release" here = the bump commit** (there's no PyPI publish): campaigns pick it up via the
  `pipx reinstall` + `gm-llm update` flow above. Make the bump its own commit, then **tag it with an
  annotated tag**: `git tag -a vX.Y.Z -m "<headline>"`.
