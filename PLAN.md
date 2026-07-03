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
- **Decision (settled): keep the internal import package `orchestrator/`** — ship as dist
  `gm-llm`, no import churn. "orchestrator" is an accurate internal name.

## 1. The decision that gates packaging: drop-in vs. installable

Today the Python code (`orchestrator/`, `tui/`, `dev/`) lives **inside** `.opencode/`, the same
dir opencode reads agents/skills from — so the app is a "drop `.opencode/` into a project" bundle.

- **Option A — keep drop-in, add a bootstrap.** Copy `.opencode/`, run a bootstrap that makes a
  venv / installs deps / runs `doctor`. Minimal refactor.
- **Option B — installable tool + scaffolded assets.** `pipx install gm-llm` gives real commands;
  `gm-llm init` scaffolds the bundled `.opencode/` agent+skill assets into the target project.
  Cleanest UX; bigger refactor (bundle assets as package data + a scaffold copier).

**Recommendation: B.** *Awaiting confirmation before the Phase 2 refactor.*

## 2. Phase 1 — native Windows portability  **[in progress]**

- **`/tmp` → OS temp dir.** Logs default to `tempfile.gettempdir()/gm-llm` (was hardcoded `/tmp`
  in `logs.py`, `tui/__main__.py`, `dev/cli.py`). **[done]**
- **opencode launch (`backend.py`).** Resolve via `shutil.which("opencode")` (native Windows may
  expose it as a `.cmd`/`.exe` shim), and create it in a new process group so it can be signalled.
  **[done]**
- **Server shutdown (`backend.py`).** `signal.SIGINT` isn't portable → `CTRL_BREAK_EVENT` on
  Windows, `SIGINT` elsewhere, `kill()` fallback. **[done]**
  - *Probe on a real Windows box:* child-process-tree teardown (opencode spawns a runtime;
    `kill()` may not reap it — may need `taskkill /T` or a Job Object).
- **Terminal:** require **Windows Terminal / PowerShell** (Textual + rich auto-enable VT there;
  legacy `cmd.exe` renders poorly). Document, don't code.

## 3. Phase 2 — packaging for easy setup (all platforms)  **[blocked on the A/B decision]**

- **`pyproject.toml`**: `name = "gm-llm"`, pinned `rich`/`textual`, console entry points.
- **`gm-llm doctor`**: checks `opencode` on PATH, Node/Bun runtime, a configured provider
  (agents pin `opencode/mimo-v2.5-free`), and port `4181` free — prints exactly what's missing.
  The single biggest setup lever on any OS.
- **README quickstart + prereqs.**

## 4. Phase 3 — validate on native Windows

Windows Terminal + PowerShell → `doctor`, server boot/**clean** stop, TUI render, and a full
**setup → play → wrap** loop. Probe the risks: `opencode.cmd` resolution, process-tree kill,
paths with spaces, ANSI.

## Open decisions (need your call)

1. ~~Package rename `orchestrator` → `gm_llm`?~~ **Settled: keep `orchestrator`.**
2. **Option A (drop-in + bootstrap) vs. B (installable + `gm-llm init`)?** *(rec: B)*
3. **CLI surface:** keep subcommands (`status/play/prep/reconcile/tui/lint`) under `gm-llm`,
   single entry point? Any renames?
4. **Provider/model:** keep `mimo-v2.5-free` as the default, or make it configurable (and have
   `doctor` validate it)?

## Biggest external unknown

opencode's **native-Windows maturity** — clean server lifecycle and child-process teardown.
Everything in our code is fixable; this one needs a real Windows box. Fallback (WSL ruled out):
pin a known-good opencode version and document it.
