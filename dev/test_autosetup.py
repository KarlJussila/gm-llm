#!/usr/bin/env python3
"""Exercise the scripted setup player without a model: the script's parsing, the brief sent
verbatim, the one priming message, and the character file brought to character creation."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator.autosetup import SetupPlayer, SetupScriptError, load_script
from gm_llm.orchestrator.setup import Setup

SCRIPT = """---
character: dallid.md
max-turns: 3
---
## Brief
Epic fantasy, level 5-20.

## How I answer
Approve a pitch that fits.
"""


class Backend:
    def __init__(self):
        self.prompts = []

    def prompt(self, sid, agent, message, **kwargs):
        self.prompts.append((sid, agent, message))
        return f"  reply {len(self.prompts)}\n"


def test_script(d):
    (d / "dallid.md").write_text("# Dallid\nA wizard.\n", encoding="utf-8")
    (d / "setup.md").write_text(SCRIPT, encoding="utf-8")
    s = load_script(d / "setup.md")
    assert s.brief == "Epic fantasy, level 5-20.", s.brief
    assert s.character == d / "dallid.md" and s.max_turns == 3
    assert s.text.startswith("## Brief") and "Approve a pitch" in s.text

    (d / "bad.md").write_text("---\ncharacter: nobody.md\n---\n", encoding="utf-8")
    try:
        load_script(d / "bad.md")
    except SetupScriptError:
        pass
    else:
        raise AssertionError("a missing character file is refused")
    return s


def test_player(script):
    b = Backend()
    p = SetupPlayer(b, "sp", script)
    assert p.answer("What campaign would you like?") == script.brief and not b.prompts
    assert p.answer("Here's a pitch.") == "reply 1"
    first = b.prompts[0][2]
    assert b.prompts[0][:2] == ("sp", "setup-player")
    for part in ("Approve a pitch", "# Dallid", "campaign/documents/dallid.md",
                 "What campaign would you like?", script.brief, "<dm>\nHere's a pitch.\n</dm>"):
        assert part in first, part
    assert p.answer("Who are you playing?") == "reply 2"
    assert b.prompts[1][2] == "<dm>\nWho are you playing?\n</dm>", b.prompts[1][2]
    assert p.exhausted


def test_character_brought(d, script):
    root = d / "campaign-dir"
    (root / "campaign").mkdir(parents=True)
    setup = Setup(None, None, str(root), character_file=script.character)
    setup._bring_character()
    dest = root / "campaign" / "documents" / "dallid.md"
    assert dest.read_text(encoding="utf-8") == "# Dallid\nA wizard.\n"
    dest.write_text("edited by the dm\n", encoding="utf-8")
    setup._bring_character()
    assert dest.read_text(encoding="utf-8") == "edited by the dm\n", "never overwritten"


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        script = test_script(d)
        test_player(script)
        test_character_brought(d, script)
    print("OK — autosetup: the script, the brief, the priming, the character file.")
