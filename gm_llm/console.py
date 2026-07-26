"""
The console frontend's shared vocabulary — and the backend lifecycle every model-calling
command runs inside.

One tiny rendering vocabulary (`note`/`warn`/`fail` for harness chatter, `banner` for the
big beats, `verdict`/`show_turn`/`show_prep` for gate results) so every command reads the
same way, and `with_engine` so every command boots, taps, and tears down `opencode serve`
identically. Both were `dev/cli.py`'s; they live here now because the commands that use
them are split across the CLI's top level (`play --ui console`) and its dev group.

This is the *console* frontend. The TUI renders the same events through
`gm_llm/tui/`; nothing here should grow logic a frontend-agnostic caller needs.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .orchestrator import Backend, BackendError, CanonPreloader, Gate, Logs
from .orchestrator.logs import debug_enabled
from .orchestrator.stream import EventTap

_COLOR = sys.stdout.isatty()


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def note(msg):
    print(c("2", f"[harness] {msg}"), flush=True)


def warn(msg):
    print(c("33", f"[harness] {msg}"), flush=True)


def fail(msg):
    print(c("1;31", f"[harness] {msg}"), flush=True)


def banner(msg):
    print(c("1;36", f"\n━━━━━ {msg} ━━━━━"), flush=True)


def speaker(label, color, text):
    print(c(color, f"\n━━━━━ {label} ━━━━━") + f"\n{text}\n", flush=True)


def verdict(label, v, *, extra="", show_report=True):
    """One gate verdict, rendered the same way everywhere: the status line, the report body
    when it failed, and the defaulted note when the checker gave no usable verdict (passed
    by default — surfaced so a checker not doing its job doesn't disappear silently)."""
    status = "passed" if v.passed else "violations"
    tail = f" · {extra}" if extra else ""
    print(c("33", f"┄┄ {label}: {status}{tail} ┄┄"), flush=True)
    if show_report and not v.passed:
        print(c("2", v.report.strip()), flush=True)
    if getattr(v, "defaulted", False):
        print(c("1;31", f"┄┄ note: {v.check} gave no usable verdict — passed by default ┄┄"),
              flush=True)


def show_turn(tr):
    """A play turn's gate summary (canon + conduct on one line, reports beneath)."""
    g = tr.gate
    nv = "passed" if g.narrative.passed else "violations"
    cv = "passed" if g.conduct.passed else "violations"
    status = "CORRECTED" if tr.corrected else "clean"
    print(c("33", f"┄┄ gate: canon {nv} · conduct {cv} · {status} · "
                  f"{g.canon_sections} canon sections ┄┄"), flush=True)
    for label, v in (("CANON", g.narrative), ("CONDUCT", g.conduct)):
        if not v.passed:
            print(c("2", f"{label}:\n{v.report.strip()}"), flush=True)
        if getattr(v, "defaulted", False):
            print(c("1;31", f"┄┄ note: {v.check} gave no usable verdict — "
                            f"passed by default ┄┄"), flush=True)


def show_prep(pr, *, show_report=True):
    """A PrepResult, rendered identically whether prep ran alone or after a reconcile."""
    extra = (f"{'CORRECTED' if pr.corrected else 'clean'} · "
             f"{'committed' if pr.committed else 'uncommitted'} · "
             f"{pr.gate.canon_sections} canon sections")
    verdict(f"check-plan (session {pr.n})", pr.gate.narrative, extra=extra, show_report=show_report)
    banner(f"session {pr.n} planned ({len(pr.plan)} chars)")


def with_engine(args, body, *, default_timeout=360):
    """Run `body(backend, gate, logs)` inside the one backend lifecycle every model-calling
    command shares: boot `opencode serve`, optionally attach the live stream tap, guarantee
    shutdown, and turn BackendError / Ctrl-C into a clean exit code. `logs` is the
    campaign's log bundle (see `orchestrator/logs.py`); GM_LLM_DEBUG=1 turns on the raw
    per-reply dump.

    `default_timeout` is the per model-call socket timeout when the user hasn't overridden
    it. Runtime turns are short, but a between-session stage can be one long dm call and
    needs a generous ceiling — the POST response only lands when the whole pass finishes,
    so too short a timeout kills a working call and the retry re-runs it."""
    timeout = args.turn_timeout or default_timeout
    note(f"starting opencode serve on :{args.port} (dir={args.dir}, call-timeout={timeout}s)")
    logs = Logs.under(project=args.dir, debug=debug_enabled())
    backend = Backend(args.dir, port=args.port, min_call_gap=args.min_gap,
                      turn_timeout=timeout, logs=logs)
    backend.on_retry = lambda agent, attempt, wait, reason: warn(
        f"{agent} call failed: {reason} — retry {attempt} in {wait}s")
    tap = None
    code = 0
    try:
        backend.start()
        if args.stream:
            tap = EventTap(backend.base, backend.directory).start()
            note("streaming live model output (--stream)…")
        body(backend, Gate(backend, CanonPreloader(args.dir), logs=logs), logs)
        if logs.archive and logs.archive.path.is_file():
            note(f"score archive: {logs.archive.path}")
        note("done.")
    except BackendError as e:
        fail(f"backend gave up: {e}")
        note("(likely still rate-limited — try `python -m gm_llm dev ping`)")
        code = 1
    except KeyboardInterrupt:
        print(flush=True)
        note("interrupted.")
        code = 130
    finally:
        if tap:
            tap.stop()
        note("shutting down server…")
        backend.stop()
    sys.exit(code)


def sessions_dir(directory) -> Path:
    return Path(directory) / "campaign" / "sessions"
