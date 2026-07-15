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
- The [opencode](https://opencode.ai) CLI, authenticated to a model provider (`opencode auth login`).
- A JS runtime — **bun** or **node** — for opencode and the plugin dependency.
- **Python 3.10+**. [pipx](https://pipx.pypa.io) is a convenient way to install the command, but plain `pip` works too.

**Install the command** (on Windows, prefer the [one-line installer](#windows-native--one-line-install) below)
```
git clone https://github.com/KarlJussila/gm-llm.git
cd gm-llm
pipx install .                # installs the `gm-llm` command (or: pip install .)
```

**Scaffold and run a campaign**
```
gm-llm init ../my-campaign    # scaffold .opencode/ and install its plugin deps (a sibling dir)
cd ../my-campaign

opencode auth login           # authenticate opencode to your model provider (once)
gm-llm doctor                 # verify opencode / runtime / port / project
gm-llm play                   # launch the TUI — setup runs on first play
```

`gm-llm init` installs the `.opencode` plugin deps for you with the first package manager it
finds (npm / bun / pnpm / yarn); pass `--no-install` to skip and do it yourself.

`gm-llm play` (or a bare `gm-llm`) is the everyday command. `dev/cli.py` still carries the
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
`gm-llm update` overwrites the framework files (agents, skills, plugin, templates) and refreshes the
plugin deps, while leaving your `campaign/` data, `.orchestrator` markers, and `node_modules`
untouched. `gm-llm --version` shows what the tool is on.

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
gm-llm init                  # scaffold this folder + install its plugin deps
gm-llm play                  # launch the game (setup runs on first play)
```
Open a **new terminal** for those so `gm-llm` is on your PATH, and use **Windows Terminal** (the
installer adds it) — the legacy `cmd.exe` console renders the Textual interface poorly.

<details><summary>Manual prerequisite steps (if you'd rather not run the script)</summary>

Run these, then follow **Install the command** and **Scaffold and run** above:
```
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS
npm install -g --allow-scripts=opencode-ai opencode-ai   # the opencode CLI

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

No opencode / no model? From a source checkout, `python dev/cli.py tui` runs the same
UI against a scripted mock (`--setup` to demo the new-campaign flow).

### The TUI

- **Header** — the current phase/mode (`SETUP`, `ACTION mode`, `META mode`) plus a live
  `ctx 47% (78k/168k)` readout of how full the runner session's context is. As it approaches
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

`dev/cli.py` is one dispatcher over the same orchestrator core. Every command targets
a campaign project via `--dir` (default: the current directory):

```
status                                 where the campaign stands (disk only, no model)
play       [--turns 6] [--resume]      drive the gated loop with the scripted player agent
prep       [--session N] [--no-commit]                     PRE: author + gate + commit the plan
reconcile  [--session N] [--no-commit] [--no-prep] [--fresh]   POST: the staged pipeline
tui        [--live] [--setup] [--theme …]                  the Textual app
lint       [--dir …]                   entity-completeness lint, standalone
ping       [N]                         probe the model's rate-limit state
```

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
                         agent/  skills/  plugin/  templates/  package.json
  orchestrator/        the Python orchestrator (over `opencode serve`)
  tui/                 the Textual app
dev/                   the developer CLI + test harness (not shipped)
install.ps1            the native-Windows one-line installer
```

**A campaign project** is what `gm-llm init` creates — a separate git repo:

```
my-campaign/
  .opencode/           the opencode assets (copied from the tool) + node_modules — gitignored
  campaign/            the generated, human-readable campaign data and play history
```

The orchestrator commits to the campaign repo at each phase boundary (`campaign: init` /
`campaign: session N plan` / `campaign: post-session N updates`). The `campaign/` data is
created on first play (setup) from `gm_llm/assets/opencode/templates/campaign/`.

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
| `player` | primary | Test harness only — a scripted autoplayer for `cli.py play`. |

Both primary agents hold **spoiler discipline**: the human is the player and hasn't read
the planning files; secrets live in files, never in conversation. The boundary is data,
not vibes — the PC knowledge ledger (`characters/{slug}.knowledge.md`) plus `[hidden]`
flags decide what can be said.

### Skills (`skills/`)

Skills hold the procedures; agents stay thin. Groups:

- **Authoring contract:** `canon-conventions` (+ its `templates/`) — the format every
  canon writer follows.
- **Setup:** `campaign-setup` (cross-cutting standards), `campaign-intake`,
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
E feedback analyst: curate campaign/feedback/*              gate: check-feedback
D1 canon  dm: file new/changed entities                     deterministic completeness lint
D2 arcs   dm: one dispatch PER ARC (code-enumerated;
          untouched arcs are a cheap no-op) + a close pass
          (new minor arcs, threads dashboard, sweep)
D3 state  dm: knowledge ledger, reveal flags, snapshots
          gate: check-propagation (the whole apply)
commit    code
F prep    dm (same warm thread): plan session N+1           gate: check-plan
```

**Setup** mirrors it: scaffold (pure Python) → interactive intake/world and character
stages (the dm signals completion with the `task_complete` tool) → arc/state dispatches →
`check-init` gate → `campaign: init` commit → session-1 prep. Every phase announces its
stages over one `on_stage` protocol, which is what the TUI's ticker renders.

### Plugins (`plugin/`)

- `dice-roller.ts` — the `dice` tool: a full TTRPG dice-expression evaluator (explode,
  keep/drop, reroll, success pools, `adv`/`dis`, …).
- `task-complete.ts` — `task_complete`: the model's explicit "this process is finished"
  signal; the orchestrator reads the call, never the prose.
- `report-findings.ts` — `report_findings`: the checker's structured verdict
  (`report` + `verdict`), read from the tool call — no text parsing.

### The feedback loop

The runner collects player feedback at every session close (verbatim, into the digest);
the analyst distills it into `campaign/feedback/{skill}.md` standing guidance
(`check-feedback`-gated); every skill and primary agent reads its own file as binding.
The system adapts to the player without the framework changing.

## Development

From a source checkout (`python -m venv .venv && .venv/bin/pip install -e .`):

```sh
.venv/bin/python dev/test_completeness.py     # lint unit checks
.venv/bin/python dev/cli.py tui               # offline TUI (mock play/wrap)
.venv/bin/python dev/cli.py tui --setup       # offline TUI (mock new-campaign setup)
.venv/bin/python dev/cli.py play --turns 6 --dir ../my-campaign   # scripted player vs. the real model
```

Model-facing `dev/cli.py` commands target a `gm-llm init`-ed campaign project via
`--dir` (default: the current directory).

`SPEC.md` describes what the system is; `PLAN.md` is the active design doc (what's in
flight and why). The mock layer (`gm_llm/orchestrator/mock.py`) duck-types `Game`/
`Setup`/`Lifecycle` so the whole TUI runs offline.
