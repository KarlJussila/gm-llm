#!/usr/bin/env python3
"""Standalone check for the check-combat gate branch (design/combat.md § Implementation map, the gate) — no pytest, no
opencode, no model. Run me directly.

Drives the real `Gate.check` over a fake backend + preloader. The point is the C2
wiring in gate.py:

  - while `in_combat`, `check-combat` chains between `check-turn` and `check-conduct`,
    on the same (warm) session — three checks, in that order;
  - its brief carries the tracker's `committed` and `pending` frames, read straight
    off the state file (read-only — the gate never touches the mutators);
  - the combat verdict lands in `GateResult.combat`, and its failure both trips
    `violations` and gets its own `— Combat —` section in the correction brief;
  - out of combat, or with no live state file, `check-combat` does not run and
    `GateResult.combat` is None.
"""

import copy
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # so `gm_llm` imports straight from the checkout

from gm_llm.orchestrator.backend import Reply  # noqa: E402
from gm_llm.orchestrator.combat import CombatState  # noqa: E402
from gm_llm.orchestrator.gate import Gate  # noqa: E402


# ── fakes ───────────────────────────────────────────────────────────────────

class FakePreloader:
    """Stands in for CanonPreloader — a bare canon block so check-turn has a brief."""
    def build(self, narration):
        return "--- PRE-LOADED CANON ---\n### INDEX\n(none)\n\n"


class FakeBackend:
    """Records every check session opened and every brief prompted, and returns a
    scripted `report_findings` verdict keyed by the check's session title. That title
    is the check name (`create_session(check)` / `create_session("check-turn")`), so
    the script maps check → (passed, report)."""

    def __init__(self, directory, verdicts):
        self.directory = str(directory)
        self.verdicts = verdicts          # check name -> (passed, report)
        self.sessions = []                # (sid, title)
        self.briefs = []                  # (title, brief) in prompt order
        self._sid_title = {}

    def create_session(self, title=None):
        sid = f"sid-{title}-{len(self.sessions)}"
        self.sessions.append((sid, title))
        self._sid_title[sid] = title
        return sid

    def prompt_full(self, sid, agent, text, whole=False):
        title = self._sid_title[sid]
        # A check session's title IS the check name (see Gate.check / _run). For the
        # warm runtime gate all three checks share the check-turn session, so key the
        # verdict off the brief's Role line instead of the (shared) session title.
        check = _role_of(text) or title
        self.briefs.append((check, text))
        passed, report = self.verdicts.get(check, (True, ""))
        return Reply(text="", tools=frozenset({"report_findings"}),
                     tool_inputs={"report_findings": {"passed": passed, "report": report}})

    def ensure_tool(self, sid, agent, reply, *, tool, args, nudge, whole=False):
        return reply  # the scripted reply already carries report_findings


def _role_of(brief: str):
    """The check a brief is for, read off its `Role: <check>` opening line."""
    first = brief.strip().splitlines()[0] if brief.strip() else ""
    if first.lower().startswith("role:"):
        return first.split(":", 1)[1].strip().split()[0].strip(" .—-")
    return None


# ── a combat state file with a real committed→pending delta ───────────────────

def _seed_state(directory):
    """goblin-1 took 6 damage (12→6) this turn, then the closing advance moved the
    pointer pc→goblin-1. committed is the pre-action baseline; pending is after."""
    def c(cid, hp, x, y):
        return {"id": cid, "name": "goblin", "hp": hp, "hp_max": 12, "dead": False,
                "conditions": [], "reaction": True, "x": x, "y": y, "z": 0}
    committed = {
        "turn": "pc", "round": 1,
        "combatants": {
            "pc": {"id": "pc", "name": "Dallid", "hp": 30, "hp_max": 30, "dead": False,
                   "conditions": [], "reaction": True, "x": 0, "y": 0, "z": 0},
            "goblin-1": c("goblin-1", 12, 30, 0),
        },
        "initiative": ["pc", "goblin-1"], "timers": [],
    }
    pending = copy.deepcopy(committed)
    pending["combatants"]["goblin-1"]["hp"] = 6   # the action
    pending["turn"] = "goblin-1"                   # the closing advance
    CombatState(directory).save(
        {"encounter": "goblin ambush", "next_timer_id": 1,
         "committed": committed, "pending": pending})


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


# ── the scenario ──────────────────────────────────────────────────────────────

def main():
    tmp = tempfile.mkdtemp()

    # --- in combat, check-combat fails: the narration claims no hit but pending shows
    #     goblin-1 dropped 6 HP → the gate must surface a combat violation ------------
    _seed_state(tmp)
    backend = FakeBackend(tmp, verdicts={
        "check-combat": (False, "1. goblin-1 lost 6 HP in pending but the narration "
                                "describes a miss — remove the damage or narrate the hit."),
    })
    gate = Gate(backend, FakePreloader())
    res = gate.check("Your swing goes wide; the goblin ducks under it.",
                     "I attack the goblin.", in_combat=True)

    order = [t for t, _ in backend.briefs]
    check(order == ["check-turn", "check-combat", "check-conduct"],
          "check-combat chains between check-turn and check-conduct")
    check(res.combat is not None and not res.combat.passed,
          "the combat verdict is present and failing")
    check(res.violations, "a failing combat verdict trips GateResult.violations")
    brief = dict(backend.briefs)["check-combat"]
    check('"hp": 6' in brief and '"hp": 12' in brief,
          "the check-combat brief carries both frames (pending 6, committed 12)")
    check("committed" in brief and "pending" in brief,
          "the brief labels the committed and pending frames")
    cb = res.correction_brief()
    check("— Combat —" in cb and "6 HP" in cb,
          "the combat finding gets its own section in the correction brief")
    # the three checks share one session (warm) — check-turn's session is reused
    titles = [t for _, t in backend.sessions]
    check(titles == ["check-turn"], "all three runtime checks run on one warm session")

    # --- out of combat: check-combat does not run, combat verdict is None ------------
    backend2 = FakeBackend(tmp, verdicts={})
    res2 = Gate(backend2, FakePreloader()).check("She nods.", "I greet her.", in_combat=False)
    check(res2.combat is None, "no combat verdict out of combat")
    check([t for t, _ in backend2.briefs] == ["check-turn", "check-conduct"],
          "check-combat is skipped entirely out of combat")

    # --- in_combat True but no state file (closing beat raced the delete) ------------
    CombatState(tmp).delete()
    backend3 = FakeBackend(tmp, verdicts={})
    res3 = Gate(backend3, FakePreloader()).check("The last foe falls.", "(combat ends)",
                                                 in_combat=True)
    check(res3.combat is None, "no combat verdict when the state file is already gone")
    check([t for t, _ in backend3.briefs] == ["check-turn", "check-conduct"],
          "check-combat is skipped when there's no live tracker state")

    print("\nC2 check-combat gate: branch, preload, and correction wiring correct.")


if __name__ == "__main__":
    main()
