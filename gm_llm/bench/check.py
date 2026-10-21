"""
`bench check` — the after-play checker (design/benchmark.md § Check).

Play captures; this judges, offline. For each run in a batch, one rolling `play-checker` session
reads the archived turns in play order — the player's message, the DM's reply, the tools it
called, and on a combat beat the tracker's frames — and submits each turn's findings through the
`submit_checks` tool. The checker therefore sees the session only up to the turn it is judging.

Its workspace is the run's campaign as it stood before play: the run dir's first commit, which
`assemble_run` makes from the fixture, extracted under `<out>/check-ws/<run>/`. Reconcile has
rewritten the run dir since, so the run dir itself would hand the checker canon from after the
session.

Output is `checks-<run_id>.jsonl` beside the archive: a header (checker model and variant, the
instrument fingerprint, the archive), then one line per turn with its findings, or `defaulted`
when the checker made no `submit_checks` call after one nudge. The play archive is never
rewritten. Idempotent per instrument and checker model unless `force`.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from ..orchestrator import Logs
from ..orchestrator.logs import debug_enabled
from ..orchestrator.registry import FrontmatterError, split_frontmatter
from .grade import (ASSETS, _apply_model, _batch_archives, _default_backend, _quiet,
                    _read_events, _run_id_of, instrument_fingerprint)

CHECKER_AGENT = "play-checker"
WS_NAME = "check-ws"


def assemble_check_ws(run_dir, ws, *, model: str | None = None) -> Path:
    """Lay the run's pre-play state and the checker's assets into `ws`, replacing what was
    there."""
    run_dir, ws = Path(run_dir), Path(ws)
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    root = _git(run_dir, "rev-list", "--max-parents=0", "HEAD").split()[0]
    archive = subprocess.run(["git", "archive", "--format=zip", root], cwd=run_dir,
                             capture_output=True, check=True).stdout
    zipfile.ZipFile(io.BytesIO(archive)).extractall(ws)
    _git(ws, "init", "-q")   # opencode loads a directory's .opencode/ agents only in a repo

    agent_dir, plugin_dir = ws / ".opencode" / "agent", ws / ".opencode" / "plugin"
    agent_dir.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)
    agent = _apply_model((ASSETS / f"{CHECKER_AGENT}.md").read_text(encoding="utf-8"), model)
    (agent_dir / f"{CHECKER_AGENT}.md").write_text(agent, encoding="utf-8")
    shutil.copy2(ASSETS / "submit-checks.ts", plugin_dir / "submit-checks.ts")
    return ws


def checker_meta(ws) -> dict:
    """The checker's `{model, variant}`, from the workspace's agent file."""
    try:
        text = (Path(ws) / ".opencode" / "agent" / f"{CHECKER_AGENT}.md").read_text(encoding="utf-8")
        fm = split_frontmatter(text)[0] or {}
    except (OSError, FrontmatterError):
        fm = {}
    return {"model": fm.get("model"), "variant": fm.get("variant")}


def turn_message(turn: dict) -> str:
    """One archived turn as the checker reads it."""
    lines = [f'<turn ref="{_ref(turn)}">']
    if turn.get("player"):
        lines += ["<player>", turn["player"], "</player>"]
    lines += ["<dm>", turn.get("narration") or "", "</dm>",
              f"<tools>{', '.join(turn.get('tools') or []) or 'none'}</tools>"]
    combat = turn.get("combat")
    if combat:
        lines += [f'<tracker-before combatant="{combat.get("combatant")}">',
                  json.dumps(combat.get("before"), ensure_ascii=False), "</tracker-before>",
                  "<tracker-after>", json.dumps(combat.get("after"), ensure_ascii=False),
                  "</tracker-after>"]
    lines.append("</turn>")
    return "\n".join(lines)


def _ref(turn: dict) -> str:
    return f"s{turn.get('session')}t{turn.get('turn')}"


def check_archive(backend, archive, *, meta: dict, instrument: dict, force: bool = False,
                  note=_quiet) -> Path:
    """Check one run's turns in a single rolling session; returns the checks file."""
    archive = Path(archive)
    events = _read_events(archive)
    run_id = _run_id_of(events, archive.stem)
    out = archive.with_name(f"checks-{run_id}.jsonl")
    header = {"event": "header", "run": run_id, "checker": meta, "instrument": instrument,
              "archive": archive.name}
    if not force and _already_checked(out, header):
        note(f"  {out.name}: already checked with this instrument — skipping (--force redoes it)")
        return out

    nudge = (ASSETS / "nudge-submit-checks.md").read_text(encoding="utf-8").strip()
    sid = backend.create_session("bench-check")
    lines = [header]
    for turn in (e for e in events if e.get("event") == "turn"):
        ref = _ref(turn)
        reply = backend.prompt_full(sid, CHECKER_AGENT, turn_message(turn))
        reply = backend.ensure_tool(sid, CHECKER_AGENT, reply, tool="submit_checks", nudge=nudge)
        record = {"ref": ref, "session": turn.get("session"), "turn": turn.get("turn")}
        if "submit_checks" not in reply.tools:
            note(f"  {ref}: no submit_checks after the nudge — recording defaulted.")
            lines.append({**record, "defaulted": True, "findings": []})
            continue
        found = reply.tool_inputs.get("submit_checks", {}).get("findings") or []
        lines.append({**record, "defaulted": False, "findings": [
            {"ref": f"{ref}#{i}", "check": str(f.get("check", "")).strip(),
             "claim": str(f.get("claim", "")).strip(),
             "evidence": str(f.get("evidence", "")).strip(),
             "category": str(f.get("category", "")).strip(),
             "continues": str(f.get("continues", "")).strip() or None}
            for i, f in enumerate(found, 1) if isinstance(f, dict)]})
    out.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
                   encoding="utf-8")
    note(f"  {out.name}: {len(lines) - 1} turn(s), "
         f"{sum(len(line.get('findings', [])) for line in lines[1:])} finding(s)")
    return out


def _already_checked(out: Path, header: dict) -> bool:
    """Whether `out` was written by this checker model and instrument."""
    try:
        first = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    except (OSError, ValueError, IndexError):
        return False
    return (first.get("checker") == header["checker"]
            and (first.get("instrument") or {}).get("sha256") == header["instrument"].get("sha256"))


def check_batch(out_dir, *, model: str | None = None, force: bool = False, port: int = 4181,
                min_gap: float = 1.0, turn_timeout: int = 600,
                backend_factory=_default_backend, note=_quiet) -> list[Path]:
    """Check every run in a batch `out_dir`, each in its own workspace and backend (the
    workspace is that run's pre-play campaign)."""
    out_dir = Path(out_dir)
    archives = _batch_archives(out_dir)
    if not archives:
        note(f"no archives found under {out_dir} (need a batch.jsonl with archives).")
        return []
    instrument = instrument_fingerprint()
    written = []
    for archive in archives:
        run_dir = archive.parents[2]           # <run>/.opencode/logs/<archive>
        note(f"── checking {run_dir.name} ──")
        ws = assemble_check_ws(run_dir, out_dir / WS_NAME / run_dir.name, model=model)
        backend = backend_factory(ws, port=port, min_gap=min_gap, turn_timeout=turn_timeout,
                                  logs=Logs.under(project=ws, debug=debug_enabled()), note=note)
        try:
            backend.start()
            written.append(check_archive(backend, archive, meta=checker_meta(ws),
                                         instrument=instrument, force=force, note=note))
        finally:
            backend.stop()
    return written


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout
