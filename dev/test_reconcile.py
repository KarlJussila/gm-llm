#!/usr/bin/env python3
"""Standalone checks for the reconcile pipeline — no pytest, no opencode; run me directly.

Drives the real `Reconciler` over a git-backed temp campaign, a scripted backend whose
replies write the files the real agents would, and a scripted gate. Covers what code owns
in the pass: the feedback step skipped when the digest has none, the arc coverage check
and its one nudge, a resume that re-briefs only the arcs still unstamped, and the diff
each gate's correction archives.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator import Logs, Reconciler  # noqa: E402
from gm_llm.orchestrator.gate import StageGateResult, Verdict  # noqa: E402
from gm_llm.orchestrator.reconciler import player_feedback  # noqa: E402


# ── fixture ─────────────────────────────────────────────────────────────────

def _arc(slug, tier):
    return (f"---\nslug: {slug}\nname: {slug.title()}\ntype: arc\nstatus: active\n"
            f"summary: the {slug} arc\ntier: {tier}\n---\n# {slug.title()}\n")


def _arc_state(slug, n):
    return f"---\nslug: {slug}\nlayer: state\nas-of: S{n}\n---\n# {slug} — state\n"


def _campaign(root: Path, feedback: str) -> None:
    (root / "gm-llm.yaml").write_text("feedback-dir: feedback\n", encoding="utf-8")
    c = root / "campaign"
    for slug, tier in (("crown", "major"), ("rivals", "minor")):
        (c / "arcs").mkdir(parents=True, exist_ok=True)
        (c / "arcs" / f"{slug}.md").write_text(_arc(slug, tier), encoding="utf-8")
        (c / "arcs" / f"{slug}.state.md").write_text(_arc_state(slug, 0), encoding="utf-8")
    s = c / "sessions" / "1"
    s.mkdir(parents=True)
    (s / "transcript.md").write_text("# Session 1 — transcript\n", encoding="utf-8")
    (s / "digest.md").write_text(f"# Session 1\n\n## Narrative\nThings happened.\n\n"
                                 f"## Player feedback\n{feedback}\n", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "init"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, capture_output=True,
                       env={**env, "PATH": "/usr/bin:/bin"})


# ── fakes ───────────────────────────────────────────────────────────────────

class FakeBackend:
    """Records every prompt; `on` maps a brief's opening words to a side effect (the file
    writes the real agent would make)."""

    def __init__(self, directory, on=None):
        self.directory = str(directory)
        self.root = Path(directory)
        self.on = on or {}
        self.prompts = []

    def create_session(self, title):
        return f"sid-{title}"

    def preface(self, sid, text):
        pass

    def prompt(self, sid, agent, message, whole=False):
        self.prompts.append((agent, message))
        for start, action in self.on.items():
            if message.startswith(start):
                action(self.root)
        return "done"

    def patient(self, *a, **k):
        from contextlib import nullcontext
        return nullcontext()

    def sent(self, start):
        return [m for _, m in self.prompts if m.startswith(start)]


class FakeGate:
    def __init__(self, digest_ok=True, propagation_ok=True):
        self.digest_ok, self.propagation_ok = digest_ok, propagation_ok

    def check_digest(self, n):
        return StageGateResult(Verdict("check-digest", self.digest_ok,
                                       "" if self.digest_ok else "1. Dropped the toast."),
                               prompt="digest", label="Digest", session=n)

    def check_propagation(self, n):
        return StageGateResult(Verdict("check-propagation", self.propagation_ok,
                                       "" if self.propagation_ok else "1. Ledger misses the map."),
                               prompt="propagation", label="Propagation", session=n)


def _stamp(*slugs):
    def act(root):
        for slug in slugs:
            (root / "campaign" / "arcs" / f"{slug}.state.md").write_text(
                _arc_state(slug, 1), encoding="utf-8")
    return act


def _events(logs):
    return [json.loads(l) for l in logs.archive.path.read_text(encoding="utf-8").splitlines()]


def _run(root, backend, gate, logs=None):
    return Reconciler(backend, gate, logs=logs).reconcile_session(1, commit=True, prep=False)


# ── tests ───────────────────────────────────────────────────────────────────

def test_player_feedback():
    assert player_feedback("## 12. Player feedback\nNone.\n## 13. Combat\nx") == ""
    assert player_feedback("## Player feedback\n\n_None — no feedback given._\n") == ""
    assert player_feedback("# Digest\nno section here") == ""
    assert player_feedback('## Player feedback\n"More rolls."\n\n## Next') == '"More rolls."'


def test_feedback_skipped_without_any(tmp):
    _campaign(tmp, "None.")
    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("crown", "rivals")})
    _run(tmp, backend, FakeGate())
    assert not backend.sent("The player gave feedback"), "no feedback, no feedback brief"


def test_feedback_curated_when_given(tmp):
    _campaign(tmp, '"More rolls, please."')
    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("crown", "rivals")})
    _run(tmp, backend, FakeGate())
    assert len(backend.sent("The player gave feedback")) == 1
    agents = {a for a, m in backend.prompts if m.startswith("The player gave feedback")}
    assert agents == {"dm"}, "feedback curation runs on the dm thread"


def test_curated_feedback_reaches_the_store(tmp):
    """The dm curates the project's `feedback/`; what it wrote goes back to the player's store."""
    _campaign(tmp, '"More rolls, please."')
    (tmp / "gm-llm.yaml").write_text("feedback-dir: player-store\n", encoding="utf-8")

    def curate(root):
        (root / "feedback" / "dm-runner.md").write_text("Ask for more rolls.\n", encoding="utf-8")
    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("crown", "rivals"),
                                   "The player gave feedback": curate})
    _run(tmp, backend, FakeGate())
    store = tmp / "player-store" / "dm-runner.md"
    assert store.read_text(encoding="utf-8") == "Ask for more rolls.\n"


def test_arc_coverage_nudge(tmp):
    _campaign(tmp, "None.")
    logs = Logs.under(base=tmp / "logs")
    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("crown"),
                                   "These arcs are not stamped": _stamp("rivals")})
    rr = _run(tmp, backend, FakeGate(), logs)
    brief = backend.sent("Reconcile the campaign's arcs")[0]
    assert "- `crown`" in brief and "- `rivals`" in brief, "the brief lists every unstamped arc"
    nudge = backend.sent("These arcs are not stamped")
    assert len(nudge) == 1 and "- `rivals`" in nudge[0] and "crown" not in nudge[0]
    assert rr.arcs_missed == ("rivals",)
    arcs = [e for e in _events(logs) if e.get("stage") == "arcs"][0]
    assert arcs["missed"] == ["rivals"] and arcs["still_missed"] == []


def test_resume_briefs_only_unstamped_arcs(tmp):
    _campaign(tmp, "None.")
    _stamp("crown")(tmp)  # a prior run reconciled `crown` before it died
    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("rivals")})
    rr = _run(tmp, backend, FakeGate())
    brief = backend.sent("Reconcile the campaign's arcs")[0]
    assert "- `rivals`" in brief and "crown" not in brief
    assert not backend.sent("These arcs are not stamped") and rr.arcs_missed == ()


def test_corrections_archive_their_diff(tmp):
    _campaign(tmp, "None.")
    logs = Logs.under(base=tmp / "logs")

    def fix_ledger(root):
        p = root / "campaign" / "characters" / "pc.knowledge.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("- The map shows the drowned stair.\n", encoding="utf-8")

    backend = FakeBackend(tmp, on={"Reconcile the campaign's arcs": _stamp("crown", "rivals"),
                                   "The check found parts of session": fix_ledger})
    rr = _run(tmp, backend, FakeGate(digest_ok=True, propagation_ok=False), logs)
    stages = {e["stage"]: e for e in _events(logs) if e["event"] == "stage"}
    assert not stages["digest"]["corrected"] and stages["digest"]["diff"] == ""
    prop = stages["propagation"]
    assert prop["corrected"] and "+- The map shows the drowned stair." in prop["diff"]
    assert "campaign/characters/pc.knowledge.md" in prop["diff"]
    assert rr.committed, "the pass still commits after the correction"


def main():
    failures = 0
    test_player_feedback()
    print("  ✓ test_player_feedback")
    for test in (test_feedback_skipped_without_any, test_feedback_curated_when_given,
                 test_curated_feedback_reaches_the_store,
                 test_arc_coverage_nudge, test_resume_briefs_only_unstamped_arcs,
                 test_corrections_archive_their_diff):
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"  ✓ {test.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"  ✗ {test.__name__}: {e}")
    if failures:
        print(f"\nFAIL — {failures} failed")
        sys.exit(1)
    print("\nOK — reconcile: feedback skip, arc coverage and resume, correction diffs.")


if __name__ == "__main__":
    main()
