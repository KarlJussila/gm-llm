# gm-llm — a D&D campaign manager for opencode

A framework that lets an LLM design, run, and maintain a long-running solo tabletop D&D
campaign: guided campaign setup, macro-scale arc planning, live sessions, and a
post-session pipeline that folds what was played back into canon. It installs as a single
`gm-llm` command that scaffolds a new campaign project and runs it — Linux, macOS, or
native Windows.

**The one principle:** *deterministic control in code; generative work in agents.* A Python
orchestrator owns all sequencing — what runs, in what order, when it's checked, when it's
committed. Between sessions each stage is one brief, checked by code or the `narrative-checker`
with at most one bounded correction, then committed. Live play goes straight from the player to
the DM. It runs on GPT-6 Luna ([`design/luna.md`](design/luna.md)).

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
- **Manual pipx/pip install** — `git pull` in your clone, then `pipx reinstall gm-llm` (or
  `pip install . --force-reinstall`). Use `reinstall`, not `install --force`: with pipx's uv
  backend, `--force` trips over uv's refusal to overwrite an existing venv.

**Then refresh each project's assets** to match the updated tool, from inside the project:
```
gm-llm update
```
`gm-llm update` overwrites the framework files (agents, skills, plugin, templates) and removes
what older versions left in `.opencode/` (`package.json`, `node_modules`), while leaving your
`campaign/` data and `.orchestrator` markers untouched. `gm-llm --version` shows what the tool is on.

### Player settings

`gm-llm init` and `gm-llm update` create `gm-llm.yaml` in the campaign project if it's missing,
and never overwrite it.

```yaml
feedback-dir: ~/.gm-llm/feedback
subagents: sequential
```

After each session the `dm` curates the feedback you gave at its close into `feedback-dir`:
`dm-runner.md` for how sessions are run, `dm.md` for the work between them. gm-llm hands each to
its agent from then on; other files there (older versions kept one per skill) are not read. The default directory is shared
across your campaigns. `feedback-dir` accepts an absolute path, `~`, or a path relative to the
project. The agents work on a copy in the project's `feedback/`: gm-llm fills it from
`feedback-dir` when a session starts and copies back what curation changed.

Set `subagents: parallel` to let independent authoring subagents run concurrently. The default
runs one at a time for rate-limited providers.

Every agent pins its model, GPT-6 Luna at `xhigh`. To play a campaign on another, add
`model` (an opencode `provider/model`) and, optionally, `variant` (its reasoning level):

```yaml
model: opencode/glm-5.3-flash-free
variant: high
```

A `model` without `variant` runs at the model's default. `variant` alone changes the level on
the pinned model. The AI players (`--player auto` and `--setup-script`) keep their own model, so
runs on different DM models face the same player. The agent files stay as shipped, so
`gm-llm update` keeps the choice.

The campaign runs apart from your own opencode setup: the global config directory (its
`AGENTS.md`, MCP servers, plugins and skills) is left out, and each agent can load only its own
skills. Your login carries over. A provider you defined only in the global config does not, so
pick a `model` from a built-in provider.

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
guided) and pitches a world, builds it once you approve, creates your character with you,
designs the arcs, writes you a primer (`campaign/documents/primer.md`, the world as your character
knows it), plans session 1, and rolls straight into play with a prologue. Thereafter the same screen carries the whole
lifecycle: play a session, `ctrl+w` (or `/wrap`) to run the post-session pipeline and
open the next one.

No opencode / no model? `gm-llm play --mock` runs the same
UI against a scripted mock (`--setup` to demo the new-campaign flow).

Want to watch instead of play? `gm-llm play --player auto` hands the player's turns to an
autonomous player agent and renders play in the same TUI. It plays on session after session,
wrapping each and opening the next by itself; `--sessions N` stops it after N, and `--turn-cap N`
pauses a session after N turns. It keeps its own sheet and notes in the project's `player/`.

Prefer plain text? `--ui console` plays (or watches) the same campaign at a terminal prompt:
`/meta <question>`, `/wrap`, `/status`, `/roll 2d6+3`, `/quit`, and Ctrl+C cancels the call in
flight.

### The TUI

- **Header** — the current phase/mode (`SETUP`, `ACTION mode`, `META mode`) plus a live
  `ctx 39% (78k/200k)` readout of how full the runner session's context is.
- **Scene pane** — the play itself: DM narration, your lines, spoiler-free progress
  tickers (`▸ advancing the story…`) during setup and wraps.
- **Behind-the-screen pane** (`ctrl+g`) — the live model stream, tool calls, and full
  gate verdicts between sessions. Closed by default; it accumulates, so opening it mid-turn shows
  everything so far.
- **Input bar** — ACTION mode (a play turn) or META mode (`ctrl+t`, an out-of-game
  question). `/roll 2d6+3` rolls locally; `ctrl+x` cancels a mistyped turn
  and puts your message back in the box.

### The CLI

`gm-llm` is one dispatcher over the same orchestrator core. The top level is
player-facing and takes the campaign as a path (default: the current directory):

```
play    [dir] [--player human|auto] [--ui tui|console] [--mock] [--setup]
        [--setup-script FILE] [--model PROVIDER/MODEL] [--variant V]
        [--sessions N] [--turn-cap N]   (with --player auto)
serve   [dir] [--player human|auto] [--mock] [--model …]   the engine over stdio, for a frontend
status  [dir]                          where the campaign stands (disk only, no model)
tokens  [dir] [--price-in …]           token + cost usage, from opencode's own store
tokens  [dir] --sessions | --session N   per session: time, context, skills; or one step by step
init | update | doctor  [dir]
```

`--model` and `--variant` override the campaign's model (see [Player settings](#player-settings))
for one invocation. `dev autoplay`, `dev prep` and `dev reconcile` take them too.

Every frontend is a client of the engine: `play` spawns `gm-llm serve`, which speaks a JSON-lines
protocol on stdio ([`design/frontends.md`](design/frontends.md)). Write your own frontend against
it in any language.

The `dev` and `bench` groups are workshop surfaces and appear **only when running from
a source checkout** (`bench` needs `dev/fixtures/`, which isn't packaged). From a
checkout, reach them with `python -m gm_llm …`, which runs the checkout's code with no
install step. They target a campaign via `--dir`:

```
dev autoplay   [--sessions N] [--turn-cap N] [--fresh]    the autonomous player plays on
dev prep       [--session N] [--no-commit]                PRE: author + gate + commit the plan
dev reconcile  [--session N] [--no-commit] [--no-prep] [--fresh]   POST: the staged pipeline
dev lint                               entity-completeness lint, standalone
dev ping       [N]                     probe the model's rate-limit state
bench run | check | grade | report | status   the benchmark harness (design/benchmark.md)
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
`orchestrator-checks.log` (per-stage summaries), `orchestrator-check-detail.log`
(every checker call in full), `orchestrator-serve.log` (the opencode server), and
`orchestrator-raw.log` (`GM_LLM_DEBUG=1` reply dumps). Set `GM_LLM_LOG_DIR` to redirect them
anywhere; with no campaign in play they fall back to a `gm-llm/` folder under the OS temp dir.

### Scripted setup

`gm-llm play DIR --setup-script FILE` hands a new campaign's setup to the `setup-player` agent,
which answers the DM from your script while the exchange streams by in the scene pane. A `DIR`
with no `.opencode/` is scaffolded first. Setup and the planning of session 1 run unattended, and
you're asked before session 1 opens; with `--player auto`, play goes straight on. If the agent fails or runs out of answers, the keyboard takes
over.

The script is markdown:

```markdown
---
character: ~/characters/dallid.md   # optional; a relative path is from the script's folder
max-turns: 20                       # optional: answers before the keyboard takes over
---
## Brief
Your answer to the DM's opening question, sent word for word.

## How I answer
Anything else the agent should know: what you want, what you'd push back on, what you leave to
the DM.
```

The character file is copied into `campaign/documents/` as character creation opens. Without a
`## Brief`, the agent writes the first answer from the rest of the script. A campaign that's
already set up ignores the script.

## Architecture

### Layout: the framework, and a campaign

**The framework repo (this directory)** is the installable tool plus its engine:

```
gm_llm/                the pip-installable tool (cli, init, doctor, --version)
  assets/opencode/     the opencode assets it ships and copies into a project:
                         agent/  skills/  plugin/  templates/
  orchestrator/        the Python orchestrator (over `opencode serve`)
  engine/              the engine and its JSON protocol (`gm-llm serve`)
  tui/                 the Textual frontend
  consoleui.py         the console frontend
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
layout and the `canon-conventions` skill for the authoring contract (frontmatter vitals, entity
info/state file pairs, `[[slug]]` links, `[hidden:<id>]` secrets and `Known to:` lines; code
generates the `INDEX.md` registry).

What the system is, its skills and its runtime seams are in [`design/README.md`](design/README.md);
the agents and every workflow — setup, play, combat, reconcile, planning — are in
[`design/luna.md`](design/luna.md).

### Agents (`agent/`)

| Agent | Mode | Job |
| --- | --- | --- |
| `dm` | primary | Between sessions: setup, reconcile, planning. Writes every campaign file; never runs a session. |
| `dm-runner` | primary | Runs one live session — narration, NPCs, dice, combat — then stops. Reads the campaign, never writes it. |
| `helper` | subagent | General-purpose help the `dm` delegates through `task`, such as one arc's reconcile. |
| `log-extractor` | subagent | Transcript and notes → the session digest. |
| `narrative-checker` | subagent | The between-session gates (`check-*`). Reads and reports only, via `report_findings`. |
| `auto-player` | primary | The autonomous player, for `--player auto`. |
| `player` | primary | The benchmark's player. |
| `setup-player` | primary | Answers setup from a script, for `play --setup-script`. |

### Orchestrator (`gm_llm/orchestrator/`)

Python over `opencode serve`'s HTTP API.

| Module | Owns |
| --- | --- |
| `backend.py` | HTTP client: sessions, prompts, pacing, cancel/revert, timeouts |
| `play.py`, `loop.py` | `play_session` — the one session loop — and `Game`, the turn: player message in, reply out, the transcript |
| `combat.py` | The initiative-driven loop while a fight is on |
| `canon.py` | `CanonPreloader` — the runner's `<prepared-context>` and the plan checker's canon block |
| `setup.py` | INIT: the staged new-campaign flow (interactive stages end on `task_complete`) |
| `planner.py` | PRE: the dm authors the plan → `check-plan` → ≤1 correction → commit |
| `reconciler.py` | POST: the staged reconcile, with per-stage resume markers |
| `lifecycle.py` | Ties setup → play → wrap → play into one object the engine drives |
| `gate.py` | `Gate` — runs a checker in a fresh session and reads its `report_findings` verdict |
| `phase.py` | Shared phase primitives: `correct_once`, the lint correction, `refresh_campaign`, `commit_campaign` |
| `lint.py` | The canon lint, plus setup's and reconcile's coverage checks |
| `registry.py`, `reveals.py` | The generated `INDEX.md`, and flipping secrets the knowledge ledger records |
| `scaffold.py` | `scaffold_campaign` — lays down `campaign/` (pure Python) |
| `paths.py` | Where a session's files live |
| `status.py` | `campaign_status` — the disk-only snapshot behind `status` and the TUI modal |
| `archive.py` | The score-event archive the benchmark reads |
| `prompts.py` + `prompts/*.md` | Every brief the orchestrator sends a model, as reviewable prose files |
| `stream.py` | `EventTap` — the live SSE stream for the behind-the-screen pane |
| `logs.py`, `mock.py` | Logging, and an offline `Lifecycle` stand-in |

### Plugins (`plugin/`)

- `dice-roller.ts` — the `dice` tool: a full TTRPG dice-expression evaluator (explode,
  keep/drop, reroll, success pools, `adv`/`dis`, …).
- `combat-tracker.ts` — the combat tracker's tools ([`design/combat.md`](design/combat.md)).
- `task-complete.ts` — `task_complete`: the model's explicit "this process is finished"
  signal; the orchestrator reads the call, never the prose.
- `report-findings.ts` — `report_findings`: the checker's structured verdict
  (`report` + `passed`), read from the tool call — no text parsing.

## Development

From a source checkout (`python -m venv .venv && .venv/bin/pip install -e .`):

```sh
.venv/bin/python dev/test_completeness.py     # lint unit checks
gm-llm play --mock                    # offline TUI (mock play/wrap)
gm-llm play --mock --setup            # offline TUI (mock new-campaign setup)
python -m gm_llm dev autoplay --turn-cap 6 --dir ../my-campaign   # the autonomous player vs. the real model
```

Model-facing `dev` commands target a `gm-llm init`-ed campaign project via
`--dir` (default: the current directory).

The mock layer (`gm_llm/orchestrator/mock.py`) duck-types `Game`/`Setup`/`Lifecycle` so the
engine, and every frontend over it, runs offline.

Contributing or picking the work back up: **`CLAUDE.md`** has the orientation and how to run the
tests; **`ROADMAP.md`** is what remains, in order; **`design/`** is the design itself (start at
`design/README.md`).
