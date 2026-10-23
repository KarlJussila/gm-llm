"""
Canon preload — campaign files read in code and handed to a model up front.

Three readers: the runner's `<prepared-context>` at the start of a session (the plan, the PC, a
map of the campaign, the player's runner feedback); the plan checker's canon block
(`build`), framed as a head start it must still extend, since the match is by name and can miss an
entity referenced indirectly; and the dm thread's preface (`dm_guidance`), the player's guidance
for the work between sessions. Plain library code: give it the campaign dir, get text back.
"""

from __future__ import annotations

import re
from pathlib import Path

from gm_llm.settings import guidance

from . import paths
from .prompts import load
from .registry import COMPANION_SUFFIXES, scan


def dm_guidance(directory) -> str:
    """The dm thread's preface: the player's standing guidance for the work between sessions,
    fenced for the thread's first brief; '' when there is none."""
    text = guidance(directory, "dm")
    return load("dm-guidance").format(guidance=text) + "\n\n" if text else ""


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
        """The plan checker's canon block for this draft, or '' if nothing could be read:
        the baseline plus the entities the draft names."""
        sections = self._render(self._baseline() + self._matched_entities(draft))
        if not sections:
            return ""
        return load("canon-header") + "\n\n" + "\n\n".join(sections) + "\n\n--- end pre-loaded canon ---\n\n"

    def _map(self) -> str:
        """A map of campaign/ for the runner: the registry, then the files it doesn't list.
        Companion files and past sessions follow fixed patterns the map states once."""
        registered = {e.rel for e in scan(self.campaign)}
        others = sorted(
            rel for rel in (p.relative_to(self.campaign).as_posix()
                            for p in self.campaign.rglob("*.md"))
            if rel != "INDEX.md" and not rel.startswith("sessions/") and rel not in registered
            and not rel.endswith(COMPANION_SUFFIXES))
        index = self._read("INDEX.md") or ""
        index = index[index.find("\n## ") + 1:].strip()  # the tables, without the file's own title
        return load("runner-map").format(index=index, others="\n".join(f"- {r}" for r in others))

    def runner_preload(self, n: int | None = None) -> str:
        """The runner's opening working set: the session plan, the PC (sheet, state and
        knowledge ledger) and a map of the campaign — the rest it reads when a scene turns on
        it. No transcript tail — at start there is none, and on resume the orchestrator
        supplies the full transcript separately."""
        n = n if n is not None else self.latest_session_number()
        plan = self._read(paths.rel(n, "plan")) if n else None
        blocks: list[str] = []
        if plan:
            blocks.append(f"### {paths.rel(n, 'plan')}\n{plan.strip()}")
        pcs = [e.rel[:-3] for e in scan(self.campaign) if e.type == "pc"]
        blocks += self._render([f"{pc}{suffix}" for pc in pcs
                                for suffix in (".md", ".state.md", ".knowledge.md")])
        if (self.campaign / "INDEX.md").is_file():
            blocks.append(self._map())
        feedback = guidance(self.campaign.parent, "dm-runner")
        if feedback:
            blocks.append(f"### Player feedback: dm-runner\n{feedback}")
        if not blocks:
            return ""
        # Fenced in <prepared-context>…</prepared-context> so the runner reads it as its
        # working set — canon read for it, not player-facing fiction to narrate back.
        return ("<prepared-context>\n" + load("runner-header") + "\n\n"
                + "\n\n".join(blocks) + "\n</prepared-context>\n\n")
