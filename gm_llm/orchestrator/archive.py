"""
The score-event archive — the benchmark's capture layer (B0 in design/benchmark.md).

Play and the between-session stages already summarize every gate outcome into
`orchestrator-checks.log` for humans; this is the same data, structured: one JSONL
file per run, one event per turn and per stage gate. The
archive is the benchmark's ground truth — severity/category grading (`bench grade`)
is a separate post-hoc pass over it, so a rubric revision re-grades history instead
of invalidating it. The runtime CAPTURES here; it never judges.

Event stream shape (all events carry `ts`, ISO-8601 UTC):
  run    — the lazy header: run_id, schema version, gm-llm version. B1's bench
           runner follows it with a `conditions` event (models, temps, tier,
           fixture id) — emitted by the runner, not here.
  turn   — one per turn: player message, narration, tools called, context usage;
           a combat beat adds the tracker frames around it.
  stage  — one per stage gate (plan / digest / propagation / init / lint), with
           its verdict, whether a correction was dispatched, and the diff it made.
  resume — a session resume; turn numbering restarts, so analysis can tell one
           run's turns from a continuation's.
  retry  — a model call's attempt that failed (a stall, an error, an empty
           reply): the agent, its opencode session, the attempt and the reason.
           The next attempt resumes that session where it stopped.

An `Archive` rides on `Logs` (see `Logs.under`) and is threaded wherever logs
already go; components emit through `logs.archive`. Writes share `append`'s
best-effort contract — an archive failure never blocks play.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .. import __version__
from .logs import append

# Bumped when an event's meaning or required fields change — graders and reports
# key off it, so old archives stay readable forever.
SCHEMA = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def verdict_fields(v) -> dict:
    """A gate `Verdict`, flattened for the archive. The full prose report rides
    along — the grader reads it, and re-deriving it later is impossible."""
    return {"check": v.check, "passed": v.passed, "defaulted": v.defaulted,
            "report": v.report}


class Archive:
    """One run's score-event stream: JSONL, append-only, best-effort.

    The header event is written lazily on the first emit, so a run that never
    gates anything (the mock TUI, a status command) leaves no file. Re-opening
    an existing path appends without re-heading — a resumed run keeps one file.
    """

    def __init__(self, path: Path, run_id: str):
        self.path = Path(path)
        self.run_id = run_id
        self._headed = self.path.is_file()

    @classmethod
    def under(cls, base: Path) -> "Archive":
        """A fresh run's archive under the log dir: `archive-{run_id}.jsonl`,
        the run id being start-time + a short random suffix (two runs in the
        same second must not interleave one file)."""
        run_id = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                  + "-" + secrets.token_hex(2))
        return cls(Path(base) / f"archive-{run_id}.jsonl", run_id)

    def emit(self, event: str, **fields) -> None:
        """Append one event. First emit writes the `run` header ahead of it."""
        if not self._headed:
            self._headed = True
            self._write({"event": "run", "ts": _now(), "run_id": self.run_id,
                         "schema": SCHEMA, "gm_llm": __version__})
        self._write({"event": event, "ts": _now(), **fields})

    def _write(self, obj: dict) -> None:
        try:
            line = json.dumps(obj, ensure_ascii=False)
        except (TypeError, ValueError):
            return  # same never-block contract as append()
        append(self.path, line + "\n")
