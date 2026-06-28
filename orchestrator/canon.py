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

_HEADER = (
    "--- PRE-LOADED CANON — already read for you; do NOT re-read these ---\n"
    "Each `### <path>` block below is the FULL current contents of that file, read for you now. "
    "The list of `### ` paths is exactly what is already loaded. Before you call any read or grep "
    "tool, check that list: if a file appears below, use its text from here — do not re-open it. "
    "Use a read tool ONLY for a file the draft references that does NOT appear below. (The set is "
    "matched to the draft by name and can miss an entity named only indirectly or by epithet; "
    "resolve those against the INDEX block below and read just those few.)\n\n"
)


class CanonPreloader:
    def __init__(self, directory: str):
        self.campaign = Path(directory).resolve() / "campaign"

    # -- file helpers -------------------------------------------------------

    def _read(self, rel: str) -> str | None:
        p = self.campaign / rel
        try:
            return p.read_text() if p.is_file() else None
        except OSError:
            return None

    def _list(self, subdir: str, pattern: re.Pattern) -> list[str]:
        d = self.campaign / subdir
        try:
            return sorted(f"{subdir}/{f.name}" for f in d.iterdir() if pattern.search(f.name))
        except OSError:
            return []

    def latest_session_number(self) -> int | None:
        n = 0
        for rel in self._list("sessions", re.compile(r"^session-\d+-plan\.md$")):
            m = re.search(r"session-(\d+)-plan\.md$", rel)
            if m:
                n = max(n, int(m.group(1)))
        return n or None

    # -- INDEX parsing + name matching -------------------------------------

    @staticmethod
    def parse_index(text: str) -> list[dict]:
        """Rows are | slug | name | status | info|design | state | one-line |."""
        out: list[dict] = []
        is_path = lambda s: bool(s) and s != "—" and s.endswith(".md")
        for line in text.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")]
            cols = cells[1:-1]  # drop the empty edges
            if len(cols) < 5:
                continue
            slug, name, _status, info, state = cols[0], cols[1], cols[2], cols[3], cols[4]
            if not slug or slug == "slug" or slug.startswith("-"):  # header / separator
                continue
            out.append({"name": name,
                        "info": info if is_path(info) else None,
                        "state": state if is_path(state) else None})
        return out

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

    def build(self, draft: str) -> str:
        """The canon block for this draft, or '' if nothing could be read."""
        n = self.latest_session_number()
        hay = draft.lower()
        matched: list[str] = []
        for e in self.parse_index(self._read("INDEX.md") or ""):
            if not self.name_matches(e["name"], hay):
                continue
            if e["info"]:
                matched.append(e["info"])
            if e["state"]:
                matched.append(e["state"])

        baseline = (
            ["INDEX.md", "state/current.md"]
            + self._list("characters", re.compile(r"\.knowledge\.md$"))
            + self._list("arcs", re.compile(r"\.md$"))
        )

        seen: set[str] = set()
        sections: list[str] = []
        for rel in baseline + matched:
            if rel in seen:
                continue
            seen.add(rel)
            body = self._read(rel)
            if body is None:
                continue
            sections.append(f"### {rel}\n{body.strip()}")
        if n:
            t = self._read(f"sessions/session-{n}-transcript.md")
            if t:
                sections.append(f"### sessions/session-{n}-transcript.md (recent tail)\n{_tail(t, 4000)}")

        if not sections:
            return ""
        return _HEADER + "\n\n".join(sections) + "\n\n--- end pre-loaded canon ---\n\n"


def _tail(text: str, n: int) -> str:
    return text if len(text) <= n else "…\n" + text[-n:]
