#!/usr/bin/env python3
"""Golden prompt-stream test (design/benchmark.md B4) — no pytest; run me directly.

Records the exact model-facing prompt stream the orchestrator emits for one
scripted setup -> session-1 prep -> play -> handoff -> reconcile pass, driving the
REAL Setup / Planner / Game / Reconciler + the REAL Gate + the REAL CanonPreloader
over a synthetic on-disk campaign and a scripted-by-agent fake backend. Every
`backend.prompt` / `backend.prompt_full` is captured as one `{seq, agent, kind,
message}` record; the stream is diffed byte-for-byte against `dev/golden/stream.jsonl`.

    python dev/test_golden_stream.py           # regenerate + diff against the golden
    UPDATE_GOLDEN=1 python dev/test_golden_stream.py   # re-record the golden

This is the cheap regression armor for a behavior-preserving refactor (B5): if the
model-facing surface shifts, the diff fails loudly. It never changes what any prompt
says — its whole value is recording the CURRENT surface.

Determinism (see the module notes below and the report): the campaign is built at a
FIXED path inside the temp root; session ids the fake mints are a fixed counter; no
timestamp/date/random reaches a prompt (the orchestrator's `datetime.now` calls only
feed logs/markers/the archive, never prompt text). A `$ROOT` normalization scrubs the
temp path as a belt-and-braces guard and reports if it ever fired.
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # import gm_llm straight from the checkout

from gm_llm.orchestrator.backend import ContextUsage, Reply  # noqa: E402
from gm_llm.orchestrator.canon import CanonPreloader  # noqa: E402
from gm_llm.orchestrator.gate import Gate  # noqa: E402
from gm_llm.orchestrator.loop import Game  # noqa: E402
from gm_llm.orchestrator.reconciler import Reconciler  # noqa: E402
from gm_llm.orchestrator.setup import Setup  # noqa: E402

GOLDEN = REPO / "dev" / "golden" / "stream.jsonl"

# The campaign lives at a FIXED path inside the temp root, so no run-varying absolute
# path can leak into a message (and if one ever does, the $ROOT scrub below catches it).
CAMPAIGN_DIRNAME = "campaign-root"


# ── synthetic campaign content (fixed bytes) ─────────────────────────────────
# The dm and the extractor don't really write files under a fake backend, so each
# scripted reply that the orchestrator reads back from disk carries the file writes it
# stands in for (its `writes`). Kept minimal but real: complete enough that the
# CanonPreloader has entities to match and the canon lint passes clean.

_NPC = """\
---
slug: magren-soley
name: Magren Soley
type: npc
status: active
summary: the barkeep of the Crossroads Inn
full-name: Magren Soley
race: Human
pronouns: he/him
age: 52
role: Barkeep of the Crossroads Inn
affiliation: Unaffiliated
---

# Magren Soley

## Stats (rough sketch)
A tough old publican; treat as a commoner with a cudgel kept behind the bar.

## Abilities
- Knows every regular's face, debt, and secret.

## Notes
Broad-shouldered, grey-streaked hair, a rag never far from his hand.
"""

_NPC_STATE = """\
---
slug: magren-soley
layer: state
as-of: S0
---
# Magren Soley — state
- Tending the bar at the Crossroads Inn as the session opens.
"""

_FACTION = """\
---
slug: harbor-guilds
name: The Harbor Guilds
type: faction
status: active
summary: the merchant coalition that runs the docks
kind: Merchant coalition
scale: City-wide
seat: The Customs House
leadership: The Guild Council
founded: Two centuries past
---

# The Harbor Guilds
"""

_FACTION_STATE = """\
---
slug: harbor-guilds
layer: state
as-of: S0
---
# The Harbor Guilds — state
- Quietly feuding over the flooded lower wharf.
"""

_LOCATION = """\
---
slug: crossroads-inn
name: The Crossroads Inn
type: location
status: active
summary: the warm dockside tavern where play opens
kind: Tavern
region: Harbor District
setting: A warm, low-beamed common room thick with smoke
controlled-by: Magren Soley
scale: A single building
---

# The Crossroads Inn
"""

_PC_SHEET = """\
---
slug: dallid
name: Dallid
type: pc
status: active
summary: the courier bound to the satchel
race: Half-elf
class: Rogue
level: 1
ability-scores: STR 10, DEX 16, CON 12, INT 13, WIS 11, CHA 14
pronouns: they/them
---

# Dallid

## Known capabilities
- Sneak Attack, Thieves' Cant, a courier's nose for a shortcut.
"""

_PC_STATE = """\
---
slug: dallid
layer: state
as-of: S0
---
# Dallid — state
- At the Crossroads Inn with the satchel.
"""

_PC_KNOWLEDGE = """\
---
slug: dallid
layer: knowledge
as-of: S1
---
# Dallid — knowledge
- Knows Magren by reputation: fair, closemouthed, owes nobody.
- Does NOT know what the satchel truly holds.
"""

_ARC_MAJOR = """\
---
slug: the-sunken-crown
name: The Sunken Crown
type: arc
status: active
summary: the drowned regalia beneath the harbor
tier: major
---
# The Sunken Crown
The drowned regalia beneath the harbor, and who means to raise it.
"""

_ARC_MAJOR_STATE = """\
---
slug: the-sunken-crown
layer: state
as-of: S0
---
# The Sunken Crown — state
- Dormant. The satchel is the first thread.
"""

_ARC_MINOR = """\
---
slug: guild-rivalry
name: Guild Rivalry
type: arc
status: active
summary: the Harbor Guilds' cold war over the lower wharf
tier: minor
hooks-into: the-sunken-crown
---
# Guild Rivalry
The Harbor Guilds' cold war over the flooded lower wharf.
"""

_ARC_MINOR_STATE = """\
---
slug: guild-rivalry
layer: state
as-of: S0
---
# Guild Rivalry — state
- Simmering. No open moves yet.
"""

_PLAN_1 = """\
# Session 1 plan

Open in the Crossroads Inn with Magren Soley behind the bar. The satchel stirs;
Magren notices the glow. Seed the Sunken Crown without naming it.
"""

_PLAN_1_CORRECTED = """\
# Session 1 plan

Open in the Crossroads Inn with Magren Soley behind the bar (grey-streaked hair,
per canon). The satchel stirs; Magren notices the glow. Seed the Sunken Crown
without naming it.
"""

_DIGEST_1 = """\
# Session 1

## Narrative
Dallid entered the Crossroads Inn; Magren clocked the satchel's glow. Dallid pressed
him and then left into the night.

## Player feedback
"More chances to roll, please."
"""

_ARCS_RECONCILED = {
    "campaign/arcs/the-sunken-crown.state.md": _ARC_MAJOR_STATE.replace(
        "as-of: S0", "as-of: S1").replace("- Dormant. The satchel is the first thread.",
                                          "- Stirring. Magren has seen the satchel's glow."),
    "campaign/arcs/guild-rivalry.state.md": _ARC_MINOR_STATE.replace("as-of: S0", "as-of: S1"),
}

_PROLOGUE_1 = """\
Saltgate's guilds have fought over its harbour for a generation. You came for work, and a satchel
that hums at night came with you.
"""

_PLAN_2 = """\
# Session 2 plan

Dallid follows the glow toward the lower wharf; the Guild Rivalry surfaces.
"""


def _writes(root: Path) -> dict:
    """Map each scripted stage to the campaign files it stands in for (relpath under
    the project root -> content). Applied by the fake as the matching reply is served."""
    return {
        "world": {
            "campaign/world/npcs/magren-soley.md": _NPC,
            "campaign/world/npcs/magren-soley.state.md": _NPC_STATE,
            "campaign/world/factions/harbor-guilds.md": _FACTION,
            "campaign/world/factions/harbor-guilds.state.md": _FACTION_STATE,
            "campaign/world/locations/crossroads-inn.md": _LOCATION,
        },
        "char": {
            "campaign/characters/dallid.md": _PC_SHEET,
            "campaign/characters/dallid.state.md": _PC_STATE,
            "campaign/characters/dallid.knowledge.md": _PC_KNOWLEDGE,
        },
        "arc_major": {
            "campaign/arcs/the-sunken-crown.md": _ARC_MAJOR,
            "campaign/arcs/the-sunken-crown.state.md": _ARC_MAJOR_STATE,
        },
        "arc_minor": {
            "campaign/arcs/guild-rivalry.md": _ARC_MINOR,
            "campaign/arcs/guild-rivalry.state.md": _ARC_MINOR_STATE,
        },
        "plan_1": {"campaign/sessions/1/plan.md": _PLAN_1,
                   "campaign/sessions/1/prologue.md": _PROLOGUE_1},
        "plan_1_fix": {"campaign/sessions/1/plan.md": _PLAN_1_CORRECTED},
        "digest_1": {"campaign/sessions/1/digest.md": _DIGEST_1},
        "arcs_1": _ARCS_RECONCILED,
        "plan_2": {"campaign/sessions/2/plan.md": _PLAN_2},
    }


# ── scripted replies ─────────────────────────────────────────────────────────

@dataclass
class Resp:
    """One scripted backend reply for an agent's FIFO queue. `writes` (a {relpath:
    content} dict under the project root) is applied before the reply is returned —
    the on-disk side effect the real agent would have produced with its tools."""
    text: str = ""
    tools: tuple = ()
    tool_inputs: dict = field(default_factory=dict)
    writes: dict | None = None


def _pass():
    """A clean narrative-checker verdict via report_findings."""
    return Resp(text="", tools=("report_findings",),
                tool_inputs={"report_findings": {"passed": True, "report": ""}})


def _fail(report: str):
    """A violation verdict via report_findings (drives one correction pass)."""
    return Resp(text="", tools=("report_findings",),
                tool_inputs={"report_findings": {"passed": False, "report": report}})


def _task_complete(text: str, **args):
    return Resp(text=text, tools=("task_complete",),
                tool_inputs={"task_complete": args})


def _script(writes: dict) -> dict[str, list[Resp]]:
    """The whole run's replies, keyed per agent, each queue consumed in call order."""
    return {
        # The dm: setup conversation, non-interactive setup stages, plan authoring +
        # correction, then the reconcile stages and the next session's plan.
        "dm": [
            Resp("Welcome — tell me the kind of world you want to run."),           # intake brief
            Resp("A rain-soaked harbour city of rival guilds. Does that fit?"),      # pitch
            Resp("A hopeful harbour city of rival guilds. Better?"),                # revision
            _task_complete(                                                          # intake done
                "The pitch is agreed."),
            Resp("The world is built."),                                            # world
            Resp("Now let's make your character."),                                  # char brief
            _task_complete("Your rogue Dallid is ready."),                           # char done
            Resp("Arcs and opening state written."),                                 # arcs + state
            Resp("Session 1 plan written."),                                         # author-brief(1)
            Resp("Plan corrected."),                                                 # plan correction
            Resp("Feedback folded in."),                                             # curate-feedback(1)
            Resp("Entity canon updated for session 1."),                            # apply-canon(1)
            Resp("Both arcs reconciled; threads updated."),                          # apply-arcs(1)
            Resp("Ledger and state updated."),                                       # apply-state(1)
            Resp("Session 2 plan written."),                                         # author-brief(2)
        ],
        # The runner: opening + three play turns, the last closing with the handoff notes.
        "dm-runner": [
            Resp("The Crossroads Inn is warm and loud. Behind the bar, Magren Soley "
                 "works a rag over a mug. The satchel at your hip stirs."),          # opening
            Resp("Magren's eyes flick to the satchel's faint glow. \"That's not "
                 "the first I've seen,\" he says, low."),                            # turn 2
            Resp("Magren's grey-streaked hair catches the lamplight as he leans "
                 "in."),                                                             # turn 3
            _task_complete(                                                          # turn 4 (closes)
                "",
                player_message="You slip out into the harbour dark. Behind you, "
                               "Magren bolts the door. — a good place to rest —",
                notes="Dallid met Magren, who noticed the satchel's glow. Sunken "
                      "Crown seeded. Dallid left toward the wharf."),
        ],
        # The extractor: transcript -> digest (gated).
        "log-extractor": [
            Resp("Digest written for session 1.", writes=writes["digest_1"]),       # digest-brief(1)
        ],
        # The narrative-checker: every stage check, in call order (play has none). The
        # session-1 plan fails to exercise the correction path; the rest pass.
        "narrative-checker": [
            _pass(),                                                                 # check-init
            _fail("1. Describe Magren's grey-streaked hair per canon, not unnamed."),  # check-plan s1
            _pass(),                                                                 # check-digest
            _pass(),                                                                 # check-propagation
            _pass(),                                                                 # check-plan s2
        ],
    }


# The setup-stage writes are attached to the dm replies that stand in for them; the
# constant queue above keeps `writes=None` on those slots, so wire them here by index.
_DM_STAGE_WRITES = {
    4: "world",       # world build          -> world files
    6: "char",        # character confirmed -> PC files
    7: "arcs_state",  # one dispatch -> both arcs, their initial state and the primer
    8: "plan_1",      # author-brief(1)      -> session-1-plan.md and its prologue
    9: "plan_1_fix",  # plan correction      -> corrected session-1-plan.md
    12: "arcs_1",     # apply-arcs(1)        -> both arcs stamped S1
    14: "plan_2",     # author-brief(2)      -> session-2-plan.md
}


# ── the scripted-by-agent fake backend ───────────────────────────────────────

class FakeBackend:
    """Covers the whole Backend surface the flow touches: per-agent scripted reply
    queues (`prompt` / `prompt_full`), a real-logic `ensure_tool`, a fixed
    `context_usage`, deterministic `create_session` ids, and the resume stubs. Every
    prompt is recorded as a `{seq, agent, kind, message}` stream record; a reply's
    `writes` are applied to disk first, standing in for the agent's file edits."""

    def __init__(self, directory: str, script: dict[str, list[Resp]]):
        self.directory = str(directory)
        self._root = Path(directory)
        self._script = {a: list(q) for a, q in script.items()}
        self.records: list[dict] = []
        self._sid = 0
        self._seq = 0
        self._prefaces: dict[str, str] = {}
        self.on_retry = None
        self.retries = 4

    # -- recording ----------------------------------------------------------

    def _record(self, agent: str, kind: str, message: str) -> None:
        self._seq += 1
        self.records.append({"seq": self._seq, "agent": agent, "kind": kind,
                             "message": _scrub(message, self._root)})

    def _next(self, agent: str) -> Resp:
        q = self._script.get(agent)
        if not q:
            raise AssertionError(f"fake backend: no scripted reply left for agent {agent!r} "
                                 f"(seq {self._seq + 1})")
        resp = q.pop(0)
        if resp.writes:
            _apply_writes(self._root, resp.writes)
        return resp

    # -- Backend surface ----------------------------------------------------

    def create_session(self, title: str | None = None) -> str:
        self._sid += 1
        return f"sid-{self._sid}"

    def preface(self, session_id: str, text: str) -> None:
        if text:
            self._prefaces[session_id] = text

    @contextmanager
    def patient(self, stall_timeout, retries=None):  # real Backend widens budget & cuts retries; no-op here
        yield

    def prompt(self, session_id: str, agent: str, text: str, whole: bool = False) -> str:
        text = self._prefaces.pop(session_id, "") + text
        self._record(agent, "prompt", text)
        return self._next(agent).text

    def prompt_full(self, session_id: str, agent: str, text: str, whole: bool = False) -> Reply:
        text = self._prefaces.pop(session_id, "") + text
        self._record(agent, "prompt_full", text)
        r = self._next(agent)
        return Reply(r.text, frozenset(r.tools), dict(r.tool_inputs))

    def ensure_tool(self, session_id: str, agent: str, reply: Reply, *, tool: str,
                    nudge: str, args: tuple = (), tries: int = 1, whole: bool = False) -> Reply:
        # Same logic as the real Backend.ensure_tool: a no-op when the terminal tool
        # call is already present (which the script guarantees), so it never perturbs
        # the recorded stream. If the script ever regressed, the nudge would fire and
        # surface as an unexpected record.
        def satisfied(r: Reply) -> bool:
            if tool not in r.tools:
                return False
            inp = r.tool_inputs.get(tool) or {}
            return all(str(inp.get(a, "")).strip() for a in args)

        for _ in range(tries):
            if satisfied(reply):
                break
            reply = self.prompt_full(session_id, agent, nudge, whole=whole)
        return reply

    def context_usage(self, session_id: str) -> ContextUsage:
        # Fixed, so nothing that reads it can vary between runs.
        return ContextUsage(tokens=1500, context_limit=200_000)

    # Resume-path surface (unused by this flow; present for parity / safety).
    def session_valid(self, session_id: str) -> bool:
        return False

    def revert_exchange(self, session_id: str) -> bool:
        return False

    def abort(self) -> bool:
        return False


def _apply_writes(root: Path, writes: dict) -> None:
    for rel, content in writes.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ── determinism helpers ──────────────────────────────────────────────────────

_ROOT_HITS = 0  # counts $ROOT scrubs, so a real path leak is reported, not hidden


def _scrub(message: str, root: Path) -> str:
    """Belt-and-braces: replace the temp campaign root (raw and resolved) with a
    `$ROOT` token, so a stray absolute path can never make the golden run-specific.
    In the current orchestrator this never fires (canon headers are relative, briefs
    carry no absolute path) — `_ROOT_HITS` records it so any future leak is visible."""
    global _ROOT_HITS
    out = message
    for form in {str(root), str(root.resolve())}:
        if form in out:
            _ROOT_HITS += out.count(form)
            out = out.replace(form, "$ROOT")
    return out


# ── the driven flow ──────────────────────────────────────────────────────────

def record_stream(root: Path) -> tuple[list[dict], dict]:
    """Drive setup -> prep -> play -> handoff -> reconcile over the fake backend and
    the real Gate/preloader; return the recorded stream and a few flow assertions."""
    writes = _writes(root)
    writes["arcs_state"] = writes["arc_major"] | writes["arc_minor"] | {
        "campaign/documents/primer.md": "# Primer\n\nSaltgate is a harbour city of rival guilds.\n"}
    (root / "gm-llm.yaml").write_text("feedback-dir: feedback\n", encoding="utf-8")
    (root / "feedback").mkdir(exist_ok=True)
    (root / "feedback/dm.md").write_text("- Name the people the player will deal with.\n",
                                         encoding="utf-8")
    script = _script(writes)
    for i, key in _DM_STAGE_WRITES.items():
        script["dm"][i].writes = writes[key]

    backend = FakeBackend(str(root), script)
    preloader = CanonPreloader(str(root))
    gate = Gate(backend, preloader, logs=None)

    facts = {}

    # 1. Setup: scaffold -> intake -> world -> char -> arcs/state -> init gate -> commit.
    setup = Setup(backend, gate, str(root), logs=None)
    st = setup.start()
    assert not st.done, "setup should not finish on the intake brief"
    proposal = setup.turn("A rain-soaked harbour city of rival guilds.")
    assert "Does that fit?" in proposal.reply
    assert setup._stage == "INTAKE", "a pitch must wait for the player"
    revised = setup.turn("Make it more hopeful.")
    assert "hopeful" in revised.reply and setup._stage == "INTAKE"
    opened = setup.turn("Yes, that world works for me.")     # completes INTAKE, builds the world
    assert setup._stage == "CHAR" and "your character" in opened.reply
    st = setup.turn("A half-elf rogue named Dallid.")           # completes CHAR -> runs pipeline
    assert st.done, "setup should be done once init is committed"
    assert "documents/primer.md" in st.reply, "code points the player to the primer"

    # 2. Session-1 prep (Planner via finalize) — gate fails once, so a correction fires.
    setup.finalize()

    # 3. Play: opening + three turns, the last a task_complete close carrying the notes.
    game = Game(backend, preloader, logs=None, campaign_dir=str(root / "campaign"),
                session=1, transcript=True)
    opening = game.start()
    assert opening.final.startswith("Saltgate's guilds"), "session 1 leads with its prologue"
    assert "Crossroads Inn is warm" in opening.final
    transcript = (root / "campaign/sessions/1/transcript.md").read_text(encoding="utf-8")
    assert transcript.index("Saltgate's guilds") < transcript.index("Crossroads Inn is warm")
    game.turn("I watch the barkeep and let the satchel show.")
    game.turn("I ask Magren what he knows.")
    t4 = game.turn("I thank him and leave.")
    assert t4.session_complete, "turn 4 should close the session via task_complete"
    assert "harbour dark" in t4.final, "the closing narration should reach the player"

    # 4. Handoff: the notes already arrived with the close, so no prompt is sent.
    notes = game.handoff()
    assert notes and notes.is_file(), "the close should have filed notes"
    facts["notes"] = notes.read_text(encoding="utf-8")

    # 5. Reconcile session 1 (+ prep session 2).
    rr = Reconciler(backend, gate, logs=None).reconcile_session(1, commit=True, prep=True)
    assert rr.prep and rr.prep.n == 2, "reconcile should prep session 2"
    assert not rr.arcs_missed, "the arc pass should stamp every arc, so no nudge"

    # Every scripted queue must be fully drained — a leftover means the flow diverged.
    leftover = {a: len(q) for a, q in backend._script.items() if q}
    assert not leftover, f"unconsumed scripted replies: {leftover}"

    facts["records"] = len(backend.records)
    facts["root_hits"] = _ROOT_HITS
    return backend.records, facts


# ── record / diff ─────────────────────────────────────────────────────────────

def _serialize(records: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                   for r in records)


def _run_once() -> tuple[str, dict]:
    tmp = Path(tempfile.mkdtemp(prefix="gm-golden-"))
    root = tmp / CAMPAIGN_DIRNAME
    root.mkdir(parents=True)
    # Hermetic git identity, so commit_campaign never depends on ambient config.
    os.environ.setdefault("GIT_AUTHOR_NAME", "golden")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "golden@example.invalid")
    os.environ.setdefault("GIT_COMMITTER_NAME", "golden")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "golden@example.invalid")
    try:
        records, facts = record_stream(root)
        return _serialize(records), facts
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    stream, facts = _run_once()

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(stream, encoding="utf-8")
        print(f"  wrote {GOLDEN.relative_to(REPO)} — {facts['records']} records, "
              f"{len(stream)} bytes")
        if facts["root_hits"]:
            print(f"  NOTE: $ROOT scrub fired {facts['root_hits']}x — a path leaks into a "
                  f"message; investigate before trusting the golden")
        print("OK — golden re-recorded")
        return

    if not GOLDEN.is_file():
        print(f"  ✗ no golden at {GOLDEN.relative_to(REPO)} — run UPDATE_GOLDEN=1 first")
        sys.exit(1)

    expected = GOLDEN.read_text(encoding="utf-8")
    if stream == expected:
        print(f"  ✓ stream matches golden ({facts['records']} records, {len(stream)} bytes)")
        if facts["root_hits"]:
            print(f"  NOTE: $ROOT scrub fired {facts['root_hits']}x this run")
        print("\nOK — 1/1 passed")
        return

    diff = difflib.unified_diff(
        expected.splitlines(keepends=True), stream.splitlines(keepends=True),
        fromfile="golden/stream.jsonl", tofile="regenerated", n=1)
    shown = list(diff)[:60]
    print("  ✗ stream diverged from the golden:\n")
    sys.stdout.writelines(shown)
    print(f"\n  ({facts['records']} records regenerated; showing up to 60 diff lines)")
    print("\nFAIL — 0/1 passed")
    sys.exit(1)


if __name__ == "__main__":
    main()
