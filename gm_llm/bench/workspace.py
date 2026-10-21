"""
What the after-play instrument (`bench check`, `bench grade`) reads a run through: the campaign
as it stood before play, the run's turns as text, and the instrument agent's model.

A run dir's first commit is the fixture as `assemble_run` laid it in — the start of the session.
Reconcile has rewritten the run dir since, so the instrument works from that commit, never from
the run dir itself.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

from ..orchestrator.registry import FrontmatterError, split_frontmatter


def extract_commit(run_dir, dest, rev: str | None = None) -> Path:
    """Extract the run dir's tracked files at `rev` (default: its first commit) into `dest`."""
    run_dir, dest = Path(run_dir), Path(dest)
    rev = rev or _git(run_dir, "rev-list", "--max-parents=0", "HEAD").split()[0]
    archive = subprocess.run(["git", "archive", "--format=zip", rev], cwd=run_dir,
                             capture_output=True, check=True).stdout
    dest.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(archive)).extractall(dest)
    return dest


def turn_ref(turn: dict) -> str:
    return f"s{turn.get('session')}t{turn.get('turn')}"


def turn_message(turn: dict) -> str:
    """One archived turn as the instrument reads it."""
    lines = [f'<turn ref="{turn_ref(turn)}">']
    if turn.get("player"):
        lines += ["<player>", turn["player"], "</player>"]
    lines += ["<dm>", turn.get("narration") or "", "</dm>",
              f"<tools>{', '.join(turn.get('tools') or []) or 'none'}</tools>"]
    if turn.get("rolls"):
        lines.append(f"<rolls>{'; '.join(turn['rolls'])}</rolls>")
    combat = turn.get("combat")
    if combat:
        lines += [f'<tracker-before combatant="{combat.get("combatant")}">',
                  json.dumps(combat.get("before"), ensure_ascii=False), "</tracker-before>",
                  "<tracker-after>", json.dumps(combat.get("after"), ensure_ascii=False),
                  "</tracker-after>"]
    lines.append("</turn>")
    return "\n".join(lines)


def apply_model(agent_md: str, model: str | None) -> str:
    """Override the `model:` line in an instrument agent's frontmatter (`--model`)."""
    if not model:
        return agent_md
    return re.sub(r"(?m)^model:.*$", f"model: {model}", agent_md, count=1)


def agent_meta(ws, agent: str) -> dict:
    """An instrument agent's `{model, variant}`, from the workspace's agent file."""
    try:
        text = (Path(ws) / ".opencode" / "agent" / f"{agent}.md").read_text(encoding="utf-8")
        fm = split_frontmatter(text)[0] or {}
    except (OSError, FrontmatterError):
        fm = {}
    return {"model": fm.get("model"), "variant": fm.get("variant")}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout
