"""
Canon preload — ported from the turn-gate plugin (turn-gate.ts).

The narrative-checker's latency is dominated by sequential file-read round-trips:
a fixed baseline plus the entity files the draft touches, one model turn each. We
do those reads here instead — fast, local, deterministic — and hand the checker
the text up front, framed as a head start it must still extend (the match is by
name and can miss an entity referenced indirectly). The check-turn skill reads
this block and treats the `### <path>` headers as the already-loaded set.

The orchestrator owns the draft, so this is plain library code with no opencode
dependency: give it the campaign dir and a draft, get back the canon block.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import paths
from .prompts import load
from .registry import scan


class CanonPreloader:
    def __init__(self, directory: str):
        self.campaign = Path(directory).resolve() / "campaign"

    # -- file helpers -------------------------------------------------------

    def _read(self, rel: str) -> str | None:
        p = self.campaign / rel
        try:
            return p.read_text(encoding="utf-8") if p.is_file() else None
        except OSError:
            return None

    def _list(self, subdir: str, pattern: re.Pattern) -> list[str]:
        d = self.campaign / subdir
        try:
            return sorted(f"{subdir}/{f.name}" for f in d.iterdir() if pattern.search(f.name))
        except OSError:
            return []

    def latest_session_number(self) -> int | None:
        return paths.latest_session(self.campaign)

    # -- name matching --------------------------------------------------------

    @staticmethod
    def name_matches(name: str, hay: str) -> bool:
        """Match by full name and by distinctive name-words (>= 4 chars), so
        'Magren' hits 'Magren Soley'. Liberal: a false match only preloads one
        extra small file, never drops correctness."""
        base = re.sub(r"^the\s+", "", name, flags=re.I).strip()
        terms = {base} | {tok for tok in re.split(r"[\s'-]+", base) if len(tok) >= 4}
        for t in terms:
            if t and re.search(rf"\b{re.escape(t.lower())}\b", hay):
                return True
        return False

    # -- assembly -----------------------------------------------------------

    def _baseline(self) -> list[str]:
        """The standing canon every preload starts from: the registry, where play stands,
        everything about the PC, and every arc."""
        return (
            ["INDEX.md", "state/current.md"]
            + self._list("characters", re.compile(r"\.md$"))
            + self._list("arcs", re.compile(r"\.md$"))
        )

    def _matched_entities(self, text: str) -> list[str]:
        """The info + state files of every registered entity named in `text` (the PC and
        arcs are already in the baseline)."""
        hay = text.lower()
        out: list[str] = []
        for e in scan(self.campaign):
            if e.type in ("pc", "arc") or not self.name_matches(e.name, hay):
                continue
            out.append(e.rel)
            if e.state_rel:
                out.append(e.state_rel)
        return out

    def _render(self, rels: list[str]) -> list[str]:
        """Read each rel once (deduped, skipping the unreadable) into a `### ` block."""
        seen: set[str] = set()
        out: list[str] = []
        for rel in rels:
            if rel in seen:
                continue
            seen.add(rel)
            body = self._read(rel)
            if body is None:
                continue
            out.append(f"### {rel}\n{body.strip()}")
        return out

    def build(self, draft: str) -> str:
        """The checker's canon block for this draft, or '' if nothing could be read.
        Baseline + the entities the draft names + the current session's transcript tail."""
        n = self.latest_session_number()
        sections = self._render(self._baseline() + self._matched_entities(draft))
        if n:
            rel = paths.rel(n, "transcript")
            t = self._read(rel)
            if t:
                sections.append(f"### {rel} (recent tail)\n{_tail(t, 4000)}")
        if not sections:
            return ""
        return load("canon-header") + "\n\n" + "\n\n".join(sections) + "\n\n--- end pre-loaded canon ---\n\n"

    def runner_preload(self, n: int | None = None) -> str:
        """The runner's opening working set: the session plan, plus the standing canon
        and the entity files the plan names. No transcript tail — at start there is
        none, and on resume the orchestrator supplies the full transcript separately."""
        n = n if n is not None else self.latest_session_number()
        plan = self._read(paths.rel(n, "plan")) if n else None
        blocks: list[str] = []
        if plan:
            blocks.append(f"### {paths.rel(n, 'plan')}\n{plan.strip()}")
        blocks += self._render(self._baseline() + self._matched_entities(plan or ""))
        if not blocks:
            return ""
        # Fenced in <prepared-context>…</prepared-context> so the runner reads it as its
        # working set — canon read for it, not player-facing fiction to narrate back.
        return ("<prepared-context>\n" + load("runner-header") + "\n\n"
                + "\n\n".join(blocks) + "\n</prepared-context>\n\n")


def _tail(text: str, n: int) -> str:
    return text if len(text) <= n else "…\n" + text[-n:]
