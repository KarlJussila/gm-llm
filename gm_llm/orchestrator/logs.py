"""
One place that owns every log the orchestrator writes.

There are four destinations, and before this module each was wired its own way
— an env var, a constructor default (`serve_log`), a `checks_log` param threaded
through half a dozen constructors, a `detail_log` on the gate — and each writer
re-implemented the same best-effort `open(path, "a")` dance. The block
formatters were copied three times over (and had drifted: `█`/`──` in one file,
`#`/`--` in the others).

Now a single `Logs` object holds all four paths, is built once at the entry
point, and is threaded as one thing; `append()` is the lone write primitive and
`banner()` / `section()` are the shared formatters.

    logs = Logs.under(project=directory, debug=debug_enabled())
    Backend(dir, logs=logs); Gate(backend, preloader, logs=logs)
    Lifecycle(backend, gate, dir, logs=logs)
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Environment override for the log directory — an explicit user choice that wins over
# the per-project default (but not over a `base` passed in code).
LOG_DIR_ENV = "GM_LLM_LOG_DIR"

# Toggles the raw per-reply debug dump (`Logs.raw`). Read through `debug_enabled()`
# at every entry point so the flag has one name and one reader.
DEBUG_ENV = "GM_LLM_DEBUG"


def debug_enabled() -> bool:
    """Whether the raw per-reply debug dump is on (`GM_LLM_DEBUG=1`)."""
    return bool(os.environ.get(DEBUG_ENV))


def default_log_dir() -> Path:
    """The fallback log dir when no project is known — the OS temp dir, so it works the
    same on Linux, macOS, and native Windows (no hardcoded `/tmp`)."""
    return Path(tempfile.gettempdir()) / "gm-llm"


def resolve_log_dir(project=None, base=None) -> Path:
    """Where logs go, by precedence:

      1. an explicit `base` (a programmatic override),
      2. the `GM_LLM_LOG_DIR` environment variable (`~` expanded),
      3. `<project>/.opencode/logs` — beside the project's other runtime state, under a
         path the campaign repo already gitignores (so logs are never committed),
      4. `<os-temp>/gm-llm` — last resort when no project directory is known.
    """
    if base is not None:
        return Path(base)
    env = os.environ.get(LOG_DIR_ENV)
    if env:
        return Path(env).expanduser()
    if project is not None:
        return Path(project) / ".opencode" / "logs"
    return default_log_dir()


def append(path, text: str) -> None:
    """The orchestrator's single log-write primitive: best-effort append. A falsy
    path is a no-op (logging disabled), and any OSError is swallowed — a logging
    failure must never break a run."""
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except (OSError, ValueError):
        pass


def banner(title: str) -> str:
    """A titled rule opening a log block — the former per-file bars (`█`/`#`),
    unified to one look now that every block shares this helper."""
    bar = "=" * 74
    return f"\n{bar}\n  {title}\n{bar}"


def section(label: str, body: str) -> str:
    """One labelled section within a block — the former `_sec`, which had been
    copied (and had drifted) across loop, planner, and reconciler."""
    return f"\n  ── {label} {'─' * max(0, 68 - len(label))}\n\n{(body or '').strip()}\n"


@dataclass(frozen=True)
class Logs:
    """Every log destination the orchestrator writes, in one object:

      serve  — the `opencode serve` subprocess's stdout/stderr (always on; the
               Popen redirect needs a real file).
      raw    — every model reply's full part structure, for debugging findings
               split across parts. Only written when `debug` is set.
      checks — the per-turn / per-prep / per-reconcile summary blocks.
      detail — the gate's per-check model output (one block per checker call).

    Built once via `Logs.under()` at the entry point and threaded as a single
    object; each component reads the path it needs and writes through `append`.
    """

    serve: Path
    raw: Path
    checks: Path
    detail: Path
    debug: bool = False

    @classmethod
    def under(cls, base=None, *, debug: bool = False, raw=None, project=None) -> "Logs":
        """Standard filenames under the resolved log dir. Precedence (see `resolve_log_dir`):
        explicit `base` > `$GM_LLM_LOG_DIR` > `<project>/.opencode/logs` > the OS temp dir.
        `raw` overrides just the raw-dump path; `debug` toggles
        whether raw dumps are written."""
        base = resolve_log_dir(project, base)
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return cls(
            serve=base / "orchestrator-serve.log",
            raw=Path(raw) if raw else base / "orchestrator-raw.log",
            checks=base / "orchestrator-checks.log",
            detail=base / "orchestrator-check-detail.log",
            debug=debug,
        )
