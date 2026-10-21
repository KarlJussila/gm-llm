#!/usr/bin/env python3
"""`bench check` over a fake backend: one rolling session per run, turns in play order, a
pristine pre-play workspace, the checks file, the defaulted path and idempotence."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.bench import check
from gm_llm.orchestrator.backend import Backend, Reply


class FakeBackend:
    """Answers each turn from `script` (turn ref → findings, or None for no tool call)."""
    ensure_tool = Backend.ensure_tool

    def __init__(self, script):
        self.script = script
        self.sessions, self.messages = [], []
        self._last = None

    def start(self):
        return self

    def stop(self):
        pass

    def create_session(self, title):
        self.sessions.append(title)
        return f"sid-{len(self.sessions)}"

    def prompt_full(self, sid, agent, message, whole=False):
        self.messages.append((sid, agent, message))
        if message.startswith("<turn "):
            self._last = message.split('"')[1]
        findings = self.script.get(self._last)
        if findings is None:
            return Reply("I think it's fine.")
        return Reply("", frozenset({"submit_checks"}), {"submit_checks": {"findings": findings}})


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_batch(out):
    run = out / "run-1"
    (run / "campaign").mkdir(parents=True)
    (run / "campaign" / "INDEX.md").write_text("# INDEX — before play\n", encoding="utf-8")
    (run / ".gitignore").write_text(".opencode/\n", encoding="utf-8")
    git(run, "init")
    git(run, "add", "-A")
    git(run, "commit", "-m", "initial state")
    # Reconcile rewrites canon after play; the checker must not see this.
    (run / "campaign" / "INDEX.md").write_text("# INDEX — after reconcile\n", encoding="utf-8")
    git(run, "commit", "-am", "post-session updates")

    logs = run / ".opencode" / "logs"
    logs.mkdir(parents=True)
    turns = [
        {"event": "turn", "session": 1, "turn": 1, "player": "Let's begin.",
         "narration": "Rain on the inn's shutters.", "tools": []},
        {"event": "turn", "session": 1, "turn": 2, "player": "I attack the goblin.",
         "narration": "Your blade bites deep.", "tools": ["damage"],
         "combat": {"combatant": "pc", "before": {"goblin-1": {"hp": 7}},
                    "after": {"goblin-1": {"hp": 7}}}},
        {"event": "turn", "session": 1, "turn": 3, "player": "I search the body.",
         "narration": "A sealed letter.", "tools": []},
    ]
    archive = logs / "archive-1.jsonl"
    archive.write_text("".join(json.dumps(e) + "\n" for e in
                               [{"event": "run", "run_id": "r1"}, *turns]), encoding="utf-8")
    (out / "batch.jsonl").write_text(json.dumps({
        "run_dir": "run-1", "archive": "run-1/.opencode/logs/archive-1.jsonl"}) + "\n",
        encoding="utf-8")
    return archive


def main(root):
    out = root / "out"
    archive = make_batch(out)
    script = {"s1t1": [],
              "s1t2": [{"check": "combat", "claim": "Damage narrated, not applied.",
                        "evidence": "goblin-1 hp 7 before and after", "category": "rules-error",
                        "continues": ""}],
              "s1t3": None}
    backends = []

    def factory(ws, **kw):
        backends.append(FakeBackend(script))
        return backends[-1]

    [path] = check.check_batch(out, backend_factory=factory, note=lambda m: None)
    fake = backends[0]

    ws = out / "check-ws" / "run-1"
    assert (ws / "campaign" / "INDEX.md").read_text(encoding="utf-8") == "# INDEX — before play\n", \
        "the workspace is the pre-play campaign, not the reconciled run dir"
    assert (ws / ".opencode" / "agent" / "play-checker.md").is_file()
    assert (ws / ".opencode" / "plugin" / "submit-checks.ts").is_file()

    assert fake.sessions == ["bench-check"], "one rolling session per run"
    turns = [m for _, _, m in fake.messages if m.startswith("<turn ")]
    assert [t.split('"')[1] for t in turns] == ["s1t1", "s1t2", "s1t3"], "turns in play order"
    assert "sealed letter" not in turns[1], "the checker never sees a later turn"
    assert "<tracker-before" in turns[1] and "<tools>damage</tools>" in turns[1]
    assert len(fake.messages) == 4, "one nudge for the turn with no submit_checks"

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert path == archive.with_name("checks-r1.jsonl")
    header, t1, t2, t3 = lines
    assert header["event"] == "header" and header["checker"]["model"] == "openai/gpt-6-luna"
    assert header["instrument"]["sha256"]
    assert t1 == {"ref": "s1t1", "session": 1, "turn": 1, "defaulted": False, "findings": []}
    assert t2["findings"] == [{"ref": "s1t2#1", "check": "combat",
                               "claim": "Damage narrated, not applied.",
                               "evidence": "goblin-1 hp 7 before and after",
                               "category": "rules-error", "continues": None}]
    assert t3["defaulted"] is True and t3["findings"] == []

    check.check_batch(out, backend_factory=factory, note=lambda m: None)
    assert not backends[1].messages, "an already-checked run is skipped"
    check.check_batch(out, force=True, backend_factory=factory, note=lambda m: None)
    assert backends[2].messages, "--force checks it again"
    print("OK — after-play check: rolling session, play order, pristine workspace, checks file.")


if __name__ == "__main__":
    for key, value in {"GIT_AUTHOR_NAME": "test", "GIT_COMMITTER_NAME": "test",
                       "GIT_AUTHOR_EMAIL": "test@example.invalid",
                       "GIT_COMMITTER_EMAIL": "test@example.invalid"}.items():
        os.environ.setdefault(key, value)
    with tempfile.TemporaryDirectory(prefix="gm-check-") as temp:
        main(Path(temp))
