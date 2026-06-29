"""
Prompt loader — the orchestrator's model-facing briefs live as files, not code.

Every brief the orchestrator sends a model (authoring, apply, the per-turn reminder,
the checker briefs, the correction notes) lives as a `.md` file under `prompts/` and
is loaded here. Keeping them out of Python means they can be edited and reviewed as
prose, side by side, without touching code — and they stay campaign-agnostic in one
place.

Convention: a prompt *file* holds only the prose. All joining and separators between
a prompt and its runtime data (canon blocks, a transcript, a report) live in the
calling code, so trailing newlines in a file never matter — `load()` strips them.
Files with `{placeholders}` are `.format(...)`ed by the caller; files without are used
as-is.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """Return the prompt text for `name` (file `prompts/{name}.md`), trailing
    newlines stripped. Cached — prompts don't change within a run."""
    return (_DIR / f"{name}.md").read_text().rstrip("\n")
