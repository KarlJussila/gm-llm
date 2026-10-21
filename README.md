# gm-llm — a D&D campaign manager for opencode

A framework that lets an LLM design, run, and maintain a long-running solo tabletop D&D
campaign: guided campaign setup, macro-scale arc planning, live gated sessions, and a
post-session pipeline that folds what was played back into canon. It installs as a single
`gm-llm` command that scaffolds a new campaign project and runs it — Linux, macOS, or
native Windows.

**The one principle:** *deterministic control in code; generative work in agents.* A Python
orchestrator owns all sequencing — what runs, in what order, when it's checked, when it's
committed. The models only ever see one focused brief at a time:

```
dispatch one focused brief → specialized check (narrative-checker, or a deterministic
lint) → at most ONE bounded correction (never a re-gate loop) → checkpoint
```

The engine targets a modest model, so the win is structure over smarts: five small,
individually-verified dispatches beat one ten-part marathon whose quality decays before
the end.

## Quick start

`gm-llm` runs the same on Linux, macOS, and **native Windows** — the `gm-llm` commands are
identical; only the prerequisites are installed differently.

**Prerequisites**
- The [opencode](https://opencode.ai) CLI, **2.1 or newer**, authenticated to a model provider (`opencode auth login`).
- A JS runtime — **bun** or **node** — for opencode.
- **Python 3.10+**. [pipx](https://pipx.pypa.io) is a convenient way to install the command, but plain `pip` works too.

**Install the command** (on Windows, prefer the [one-line installer](#windows-native--one-line-install) below)
```
git clone https://github.com/KarlJussila/gm-llm.git
cd gm-llm
pipx install .                # installs the `gm-llm` command (or: pip install .)
```

**Scaffold and run a campaign**
```
gm-llm init ../my-campaign    # scaffold .opencode/ (a sibling dir)
cd ../my-campaign

opencode auth login           # authenticate opencode to your model provider (once)
gm-llm doctor                 # verify opencode / runtime / port / project
gm-llm play                   # launch the TUI — setup runs on first play
```

`gm-llm play` (or a bare `gm-llm`) is the everyday command. The `dev` group carries the
orchestrator power-commands (`status` / `prep` / `reconcile` / `lint`) for development.

### Updating

Two things update independently — the `gm-llm` **tool**, and each project's copy of the
**framework assets** (a project's `.opencode/` is a snapshot taken at `init` time).

**Update the tool:**
- **Windows one-liner install** — just re-run the installer; it pulls the latest and reinstalls
  into its venv.
- **Manual pipx/pip install** — `cd path/to/gm-llm && git pull && pipx reinstall gm-llm`
  (or `pip install . --force-reinstall`). Use `reinstall`, not `install --force`: with
  pipx's uv backend, `--force` trips over uv's refusal to overwrite an existing venv.

**Then refresh each project's assets** to match the updated tool:
```
gm-llm update path/to/my-campaign
```
`gm-llm update` overwrites the framework files (agents, skills, plugin, templates) and removes
what older versions left in `.opencode/` (`package.json`, `node_modules`), while leaving your
`campaign/` data and `.orchestrator` markers untouched. `gm-llm --version` shows what the tool is on.

### Player settings

`gm-llm init` creates `gm-llm.yaml` in the campaign project. `gm-llm update` preserves it.

```yaml
feedback-dir: ~/.gm-llm/feedback
subagents: sequential
```

The default feedback directory is shared across your campaigns. `feedback-dir` accepts an absolute
path, `~`, or a path relative to the project. Set `subagents: parallel` to let independent authoring
subagents run concurrently. The default runs one at a time for rate-limited providers.

### Windows (native) — one-line install

The simplest path. Open **PowerShell** and paste:
```
irm https://raw.githubusercontent.com/KarlJussila/gm-llm/main/install.ps1 | iex
```
That installs git, Python, Node, opencode, and the `gm-llm` command (all per-user, no admin —
winget may show a UAC prompt). `gm-llm` itself goes in a dedicated venv the installer puts on your
PATH, so there's no pipx to manage. It's idempotent — re-running it also updates the tool. When it
finishes it prints the commands left to start playing:
```
opencode auth login          # log in to a model provider (one time, interactive)
mkdir ~\my-campaign          # a folder for your campaign
cd ~\my-campaign
gm-llm init                  # scaffold this folder
gm-llm play                  # launch the game (setup runs on first play)
```
Open a **new terminal** for those so `gm-llm` is on your PATH, and use **Windows Terminal** (the
installer adds it) — the legacy `cmd.exe` console renders the Textual interface poorly.

<details><summary>Manual prerequisite steps (if you'd rather not run the script)</summary>

Run these, then follow **Install the command** and **Scaffold and run** above:
```
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS
npm install -g --allow-scripts=@opencode/cli @opencode/cli   # the opencode CLI (2.x)

python -m pip install --user pipx
python -m pipx ensurepath                                 # then restart the terminal
```
If winget can't find or install Python (common on older Windows 10), install Python 3.12 from
[python.org](https://www.python.org/downloads/) with **"Add python.exe to PATH"** checked.
</details>

An empty directory opens in the **setup** phase: the DM interviews you (free-form or
guided), builds the world, creates your character with you, designs the arcs, plans
session 1, and rolls straight into play. Thereafter the same screen carries the whole
lifecycle: play a session, `ctrl+w` (or `/wrap`) to run the post-session pipeline and
open the next one.

No opencode / no model? `gm-llm play --mock` runs the same
UI against a scripted mock (`--setup` to demo the new-campaign flow).

Want to watch instead of play? `gm-llm play --player auto` hands the player's turns to a
scripted agent and renders the session in the same TUI — the character packet comes from
`--character` (or a `*.player.md` beside the campaign), and `--turn-cap` bounds the run.
Add `--ui console` for the same thing as plain text.

### The TUI

- **Header** — the current phase/mode (`SETUP`, `ACTION mode`, `META mode`) plus a live
  `ctx 39% (78k/200k)` readout of how full the runner session's context is. As it approaches
  the limit the DM is steered to bring the session to a close at a natural beat (it won't rush
  the story to do so).
- **Scene pane** — the play itself: DM narration, your lines, spoiler-free progress
  tickers (`▸ advancing the story…`) during setup and wraps, and a muted per-turn status
  (`✓ checked` / `✎ corrected (canon)`) showing the gate at work.
- **Behind-the-screen pane** (`ctrl+g`) — the live model stream, tool calls, and full
  gate verdicts. Closed by default; it accumulates, so opening it mid-turn shows
  everything so far.
- **Input bar** — ACTION mode (a gated play turn) or META mode (`ctrl+t`, an ungated
  out-of-game question). `/roll 2d6+3` rolls locally; `ctrl+x` cancels a mistyped turn
  and puts your message back in the box.

### The CLI

`gm-llm` is one dispatcher over the same orchestrator core. The top level is
player-facing and takes the campaign as a path (default: the current directory):

```
play    [dir] [--player human|auto] [--ui tui|console] [--mock] [--setup]
status  [dir]                          where the campaign stands (disk only, no model)
tokens  [dir] [--price-in …]           token + cost usage, from opencode's own store
init | update | doctor  [dir]
```

The `dev` and `bench` groups are workshop surfaces and appear **only when running from
a source checkout** (`bench` needs `dev/fixtures/`, which isn't packaged). From a
checkout, reach them with `python -m gm_llm …`, which runs the checkout's code with no
install step. They target a campaign via `--dir`:

```
dev autoplay   [--turn-cap 6] [--fresh] [--character …]   the scripted player agent plays
dev prep       [--session N] [--no-commit]                PRE: author + gate + commit the plan
dev reconcile  [--session N] [--no-commit] [--no-prep] [--fresh]   POST: the staged pipeline
dev lint                               entity-completeness lint, standalone
dev ping       [N]                     probe the model's rate-limit state
bench run | grade | report             the benchmark harness (design/benchmark.md)
```

`bench run --ui tui` watches a batch in the play TUI instead of as stdout notes — a header
tracks run *k* of *N* and the outcomes so far, and each run's play, fights and reconcile
render as they would in a live session. Watching is read-only: nothing typed reaches a run
and `ctrl+w` is refused, so a watched batch's archives are what a headless batch's would be.
`ctrl+x` still cancels the call in flight (the loop asks again), and `ctrl+q` stops the batch
— the run in flight ends resumable, so `bench run --resume` picks it back up.

Defaults do the right thing: `prep` targets the next session and `reconcile` the latest
played one (inferred from disk and printed before running), and both **commit by
default** — `--no-commit` for a dry run.

Logs land in the campaign's `.opencode/logs/` (gitignored, so they're never committed):
`orchestrator-checks.log` (per-turn/per-stage summaries), `orchestrator-check-detail.log`
(every checker call in full), `orchestrator-serve.log` (the opencode server), and
`orchestrator-raw.log` (`GM_LLM_DEBUG=1` reply dumps). Set `GM_LLM_LOG_DIR` to redirect them
anywhere; with no campaign in play they fall back to a `gm-llm/` folder under the OS temp dir.

## Architecture

### Layout: the framework, and a campaign

**The framework repo (this directory)** is the installable tool plus its engine:

```
gm_llm/                the pip-installable tool (cli, init, doctor, --version)
  assets/opencode/     the opencode assets it ships and copies into a project:
                         agent/  skills/  plugin/  templates/
  orchestrator/        the Python orchestrator (over `opencode serve`)
  tui/                 the Textual app
dev/                   the developer CLI + test harness (not shipped)
install.ps1            the native-Windows one-line installer
```

**A campaign project** is what `gm-llm init` creates — a **separate git repo**, so framework
development and play history don't entangle:

```
my-campaign/
  .opencode/           the opencode assets (copied from the tool) — gitignored
  campaign/            the generated, human-readable campaign data and play history
```

The orchestrator commits to the campaign repo at each phase boundary (`campaign: init` /
`campaign: session N plan` / `campaign: post-session N updates`). The `campaign/` data is
created on first play (setup) from `gm_llm/assets/opencode/templates/campaign/`. The DM agents
run with the project root as their working directory, so any plain `git` they do lands in the
campaign repo rather than the framework's.

All campaign state is human-readable markdown — see `templates/campaign/README.md` for the
layout and the `canon-conventions` skill for the authoring contract (entity info/state file
pairs, `[[slug]]` links, the `INDEX.md` registry, `[hidden]`/`Known to:` awareness flags, and
the required `## Vitals` completeness block per entity).

### Agents (`agent/`)

| Agent | Mode | Job |
| --- | --- | --- |
| `dm` | primary | The between-sessions brain: authors world, arcs, plans, and all canon. Never runs live sessions. |
| `dm-runner` | primary | Runs one live session — narration, NPCs, dice — then stops. No planning, no note-taking (the transcript is auto-captured). |
| `narrative-checker` | subagent | The verification engine, one skill per role (`check-*`). Reads and reports only; submits verdicts via the `report_findings` tool. |
| `campaign-analyst` | subagent | Post-session assessment (`session-review`) and player-feedback curation (`feedback-curation`). |
| `log-extractor` | subagent | Transcript → structured session digest (`log-extract`), lossless. |
| `player` | primary | Test harness only — a scripted autoplayer for `gm-llm dev autoplay`. |

Both primary agents hold **spoiler discipline**: the human is the player and hasn't read
the planning files; secrets live in files, never in conversation. The boundary is data,
not vibes — the PC knowledge ledger (`characters/{slug}.knowledge.md`) plus `[hidden]`
flags decide what can be said.

### Skills (`skills/`)

Skills hold the procedures; agents stay thin. Groups:

- **Authoring contract:** `canon-conventions` (+ its `templates/`) — the format every
  canon writer follows.
- **Setup:** `campaign-intake`,
  `world-build`, `character-create`, `character-import`, `arc-design`, `state-init`.
- **Planning:** `session-plan`, pulling `encounter-plan` / `investigation-plan` /
  `npc-plan` / `pacing-plan` as the session needs them.
- **Live play (dm-runner):** `session-run` (always-on core craft), `session-flow`
  (open/pace), `session-close` (the end-of-session procedure), `social-play`, `discoveries`.
- **Post-session:** `log-extract`, `session-review`, `apply-canon`, `apply-arcs`
  (one arc per dispatch), `apply-state`, `feedback-curation`.
- **Checks (narrative-checker roles):** `check-turn`, `check-conduct`, `check-plan`,
  `check-digest`, `check-propagation`, `check-feedback`, `check-init`. The shared
  protocol (task list, report-only, `report_findings` submission) lives once in the
  agent prompt; each skill is just its role's checks.

### Orchestrator (`gm_llm/orchestrator/`)

Backend-agnostic Python over `opencode serve`'s HTTP API. Stdlib-only.

| Module | Owns |
| --- | --- |
| `backend.py` | HTTP client: sessions, prompts, pacing, cancel/revert, timeouts |
| `loop.py` | `Game` — the gated per-turn loop, the transcript, the per-turn craft reminder |
| `gate.py` | `Gate` — spawns the checker, reads its `report_findings` verdict; a missing verdict is nudged once, then passes by default (surfaced in the log) |
| `canon.py` | `CanonPreloader` — reads canon in code and hands the checker/runner a pre-loaded context block |
| `planner.py` | PRE: dm authors the plan → `check-plan` → ≤1 correction → commit |
| `reconciler.py` | POST: the staged pipeline (below) with per-stage resume markers |
| `setup.py` | INIT: the staged new-campaign flow (interactive stages signal completion via `task_complete`) |
| `scaffold.py` | `scaffold_campaign` — lays down a project's `campaign/` from the templates (pure Python) |
| `lifecycle.py` | Ties setup → play → wrap → play into one object the TUI drives |
| `phase.py` | The two shared invariants: `apply_one_correction`, code-owned `commit_campaign` |
| `completeness.py` | Deterministic entity lint (required `## Vitals` fields per type) |
| `status.py` | `campaign_status` — the disk-only campaign snapshot (the `status` command + TUI modal) |
| `prompts.py` + `prompts/*.md` | Every brief the orchestrator sends a model, as reviewable prose files |
| `stream.py` | `EventTap` — live SSE stream for the behind-the-screen pane |
| `logs.py`, `textmarkup.py`, `mock.py` | Logging, safe markup rendering, offline mocks |

**A runtime turn:** the runner drafts → one warm checker session runs `check-turn` then
`check-conduct` → violations come back as one bounded correction → the final narration is
appended to the transcript and shown to the player. Nothing reaches the player unchecked,
and the model can't forget a step it never owned.

**The post-session pipeline** (`reconcile_session(N)`), each stage its own dispatch with
a `.orchestrator/` marker so a failure resumes where it died:

```
handoff   runner (warm) writes its session notes; code files them
B digest  log-extractor: transcript → session-N.md          gate: check-digest
C assess  analyst: digest → assessment                      (analysis, no gate)
E feedback dm: curate player-level feedback                skipped when none was given
D1 canon  dm: file new/changed entities                     deterministic completeness lint
D2 arcs   dm: one dispatch PER ARC (code-enumerated;
          untouched arcs are a cheap no-op) + a close pass
          (new minor arcs, threads dashboard, sweep)
D3 state  dm: knowledge ledger, reveal flags, snapshots
          gate: check-propagation (the whole apply)
commit    code
F prep    dm (same warm thread): plan session N+1           gate: check-plan
```

**Setup** starts with a scaffold, then an interactive campaign brief and world proposal. The player
can revise the world before approving it and creating a character. One background dispatch writes
the arcs and initial state. Code checks the arc coverage and `S0` snapshots, runs the canon lint,
then asks `check-init` to review duplicates, hidden layers and consistency. The orchestrator commits
`campaign: init` and prepares session 1. Every phase announces its stages through `on_stage` for the
TUI ticker.

### Plugins (`plugin/`)

- `dice-roller.ts` — the `dice` tool: a full TTRPG dice-expression evaluator (explode,
  keep/drop, reroll, success pools, `adv`/`dis`, …).
- `task-complete.ts` — `task_complete`: the model's explicit "this process is finished"
  signal; the orchestrator reads the call, never the prose.
- `report-findings.ts` — `report_findings`: the checker's structured verdict
  (`report` + `verdict`), read from the tool call — no text parsing.

### The feedback loop

The runner collects player feedback at session close. After the digest records it, the `dm`
curates actionable points into the shared directory set by [player settings](#player-settings),
one file per skill or agent. The runner's guidance is included in its prepared context; other
guidance is read when the agent starts or loads the matching skill. These preferences override the
defaults. Benchmark runs use a private copy of the fixture's feedback.

## Development

From a source checkout (`python -m venv .venv && .venv/bin/pip install -e .`):

```sh
.venv/bin/python dev/test_completeness.py     # lint unit checks
gm-llm play --mock                    # offline TUI (mock play/wrap)
gm-llm play --mock --setup            # offline TUI (mock new-campaign setup)
python -m gm_llm dev autoplay --turn-cap 6 --dir ../my-campaign   # scripted player vs. the real model
```

Model-facing `dev` commands target a `gm-llm init`-ed campaign project via
`--dir` (default: the current directory).

The mock layer (`gm_llm/orchestrator/mock.py`) duck-types `Game`/`Setup`/`Lifecycle` so the
whole TUI runs offline.

Contributing or picking the work back up: **`CLAUDE.md`** has the orientation and how to run the
tests; **`ROADMAP.md`** is what remains, in order; **`design/`** is the design itself (start at
`design/README.md`).
