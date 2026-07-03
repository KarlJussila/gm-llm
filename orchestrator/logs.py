"""
One place that owns every log the orchestrator writes.

There are four destinations, and before this module each was wired its own way
— an env var (`ORCH_DEBUG`), a constructor default (`serve_log`), a `checks_log`
param threaded through half a dozen constructors, a `detail_log` on the gate —
and each writer re-implemented the same best-effort `open(path, "a")` dance. The
block formatters were copied three times over (and had drifted: `█`/`──` in one
file, `#`/`--` in the others).

Now a single `Logs` object holds all four paths, is built once at the entry
point, and is threaded as one thing; `append()` is the lone write primitive and
`banner()` / `section()` are the shared formatters.

    logs = Logs.under(debug=bool(os.environ.get("ORCH_DEBUG")))
    Backend(dir, logs=logs); Gate(backend, preloader, logs=logs)
    Lifecycle(backend, gate, dir, logs=logs)
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


def default_log_dir() -> Path:
    """The per-user directory for orchestrator logs — the OS temp dir, so it works
    the same on Linux, macOS, and native Windows (no hardcoded `/tmp`)."""
    return Path(tempfile.gettempdir()) / "gm-llm"


def append(path, text: str) -> None:
    """The orchestrator's single log-write primitive: best-effort append. A falsy
    path is a no-op (logging disabled), and any OSError is swallowed — a logging
    failure must never break a run."""
    if not path:
        return
    try:
        with open(path, "a") as f:
            f.write(text)
    except OSError:
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
    def under(cls, base=None, *, debug: bool = False, raw=None) -> "Logs":
        """Standard filenames under `base` (the OS temp dir by default — cross-platform,
        so no hardcoded `/tmp`). `raw` overrides just the raw-dump path (the old
        `ORCH_DEBUG_LOG`); `debug` toggles whether raw dumps are written."""
        base = Path(base) if base is not None else default_log_dir()
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
