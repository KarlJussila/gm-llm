# PLAN — cross-platform (native Windows) + easy setup

The active work-in-flight doc. `SPEC.md` describes what the system *is*; this describes
the work in flight. The prior plan (the `orchestrator` staged-pipeline rework and init
integration) is fully built — that history lives in git and in `SPEC.md`.

> **Carried over from the prior plan (still owed):** a **live-model shakedown** — a real
> new-campaign run (setup + a character import) and a post-session pass against the model,
> exercising the per-arc apply briefs and the slimmed checker skills. Not blocking this work.

## Goal

Make `gm-llm` easy for anyone to install and run — **including native Windows** (no WSL) —
instead of a Linux venv with clunky CLI commands.

## Why it's feasible

The architecture is portability-friendly: a Python orchestrator that talks to `opencode
serve` over HTTP on `127.0.0.1`. Python deps are tiny and cross-platform (`rich`, `textual`,
+ stdlib); there are **no** Unix-only modules (`curses`/`fcntl`/`pty`/`fork`/`termios`). The
real external dependency is **`opencode`** itself (a Node/Bun app the backend shells out to),
which ships cross-platform.

## 0. Naming → `gm-llm`

Standardize the **product/tool** name on `gm-llm`. Leave **domain nouns** alone — the generated
`campaign/` data dir, "session", "arc" are the subject matter, not the product.

- CLI `prog` + docstring (`dev/cli.py`), TUI titles (`tui/__main__.py`), doc titles
  (`README.md`, `SPEC.md`). **[done in the first increment]**
- **Decision (revised): the engine and UI live under the tool package** — `gm_llm.orchestrator`
  and `gm_llm.tui`. The earlier "keep top-level `orchestrator/`" call shipped generic
  top-level packages (`orchestrator`, `tui`) into site-packages, colliding with any other
  distribution using those names; one mechanical import sweep fixed it.

## 1. Packaging model — **Option B, chosen and built**

`gm-llm` is an installable tool (`pipx install .`) whose `init` scaffolds the bundled opencode
assets into a target project's `.opencode/`. The Python code (`gm_llm/`, with the engine and
UI as `gm_llm.orchestrator` / `gm_llm.tui`)
is packaged; the opencode assets live under `gm_llm/assets/opencode/` and are copied by `init`.
The source repo is no longer itself a drop-in `.opencode/` — dogfood via `gm-llm init` + `gm-llm play`.

## 2. Phase 1 — native Windows portability  **[in progress]**

- **`/tmp` → OS temp dir.** Logs default to `tempfile.gettempdir()/gm-llm` (was hardcoded `/tmp`
  in `logs.py`, `tui/__main__.py`, `dev/cli.py`). **[done]**
- **opencode launch (`backend.py`).** Resolve via `shutil.which("opencode")` (native Windows may
  expose it as a `.cmd`/`.exe` shim), and create it in a new process group so it can be signalled.
  **[done]**
- **Server shutdown (`backend.py`).** `signal.SIGINT` isn't portable → `taskkill /F /T` on
  Windows (reaps the shim's whole process tree; a graceful CTRL_BREAK risked cmd's
  "Terminate batch job?" prompt hanging shutdown), `SIGINT` elsewhere, `kill()` fallback. **[done]**
- **Terminal:** require **Windows Terminal / PowerShell** (Textual + rich auto-enable VT there;
  legacy `cmd.exe` renders poorly). Document, don't code.

## 3. Phase 2 — packaging for easy setup  **[built]**

- **`pyproject.toml`** — dist `gm-llm`, pinned `rich`/`textual`, console entry point
  `gm-llm = gm_llm.cli:main`, package-data for the orchestrator prompts and the bundled assets. **[done]**
- **`gm_llm` package** — `play` (launch TUI; bare `gm-llm` too), `init` (scaffold), `doctor`
  (opencode / JS runtime / plugin installer / port / project-init checks). **[done]**
- **README quickstart** rewritten to the install→init→doctor→play flow. **[done]**
- **CLI surface (decided):** `gm-llm` carries `play`/`init`/`doctor`; the orchestrator
  power-commands stay in `dev/cli.py` for now — this is where future player features
  (talk to the DM to fix canon, roll a campaign back) will grow.

### Still to do in Phase 2 — **model configuration** *(deferred, by agreement)*

Default stays `mimo`. Add a way to pick another model. Sketch: `gm-llm init --model <id>` writes
the chosen id into the scaffolded agents' frontmatter (default `opencode/mimo-v2.5-free`), and
`doctor` prints the configured model. Later: a project config re-key without re-init. *(No design
blocker — just not built yet.)*

## 4. Phase 3 — validate on native Windows

Windows Terminal + PowerShell → `doctor`, server boot/**clean** stop, TUI render, and a full
**setup → play → wrap** loop. Probe the risks: `opencode.cmd` resolution, process-tree kill,
paths with spaces, ANSI.

## Decisions — all settled

1. ~~Package rename?~~ **`gm_llm.orchestrator` / `gm_llm.tui`** (revised — see §0).
2. ~~Packaging model?~~ **Option B (installable + `gm-llm init`).** Built.
3. ~~CLI surface?~~ **`gm-llm` = play/init/doctor; power-commands stay in `dev/cli.py`.**
4. ~~Model config?~~ **Default `mimo`; configurable model deferred to its own increment (above).**

## Biggest external unknown

opencode's **native-Windows maturity** — clean server lifecycle and child-process teardown.
Everything in our code is fixable; this one needs a real Windows box. Fallback (WSL ruled out):
pin a known-good opencode version and document it.
