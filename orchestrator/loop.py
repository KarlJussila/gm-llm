"""
The per-turn loop — the heart of the pivot.

The orchestrator, not the model, drives every turn: the runner drafts, the gate
ALWAYS runs, and on violations the runner gets exactly ONE bounded correction pass
before the result is returned. No tool the model can forget to call; no re-check
loop; nothing reaches the player (or the benchmark's scorer) until the loop says so.

The orchestrator also owns the **transcript**: because it holds each turn's final
messages, it writes `campaign/sessions/session-{N}-transcript.md` itself — the
player's message and the *corrected* DM narration per turn, never the discarded
draft or the gate's correction chatter. (This replaces the old capture plugin, which
recorded the raw runner session — drafts, corrections and all.) `log-extractor` then
reads this clean record after the session.

It also owns the **per-turn craft reminder**: the turn algorithm (agency, ask-for-a-
roll, narrate-the-response) rides in front of each player message, fresh every turn
so it can't decay over a long session. (This replaces the old `dm-reminder` plugin,
which pushed the same loop into the system prompt — the user message is more salient
and the orchestrator already drives the prompt.)

`Game` is the headless core. Interfaces (the TUI, the benchmark) drive it:
  g = Game(backend, gate)
  g.start()                 # runner opens the scene (gated)
  g.turn(player_input)      # one full gated turn -> TurnResult
  g.meta(question)          # out-of-game question, answered ungated
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_TURN_REMINDER = (
    "<turn-reminder>\n"
    "Per-turn DM craft — run this on EVERY player message, in order:\n"
    "1. Out-of-game question (a rule, logistics, \"how much longer?\")? Answer it plainly and "
    "spoiler-free, then stop.\n"
    "2. Otherwise the player declared what THEIR CHARACTER says or does. Never speak or act for the "
    "character. Ambiguous? Ask. If they overstep (narrating an NPC or the world, or an ability the "
    "character plainly lacks), step out of game and say so — don't play it as done.\n"
    "3. ASK FOR A ROLL — and ask frequently. If the action involves ANY skill, uncertainty, or "
    "chance of failure (even when success is likely), or the player is trying to find/perceive "
    "something, recalling what their character would know about a subject, or persuading/deceiving "
    "an NPC — name the fitting skill and ask the PLAYER to roll. Don't hand success or information "
    "over for free; when in doubt, ask. Don't announce a DC. Then set the outcome from BOTH the "
    "task's difficulty AND the value they report — success and failure are a gradient, not just "
    "pass/fail.\n"
    "4. Write the world's and the NPCs' response — not the character's next move — as your reply.\n"
    "</turn-reminder>"
)

_RESUME_PRIME = (
    "This session is already in progress. Below is the play so far — the established record of "
    "everything that has happened, your own narration included. Absorb it as canon you have already "
    "narrated. Do NOT summarize it, re-narrate it, or open a new scene; the player has lived all of "
    "it. Reply only with a one-line acknowledgement that you are caught up, then wait — the player's "
    "next message continues seamlessly from the final beat below.\n\n--- PLAY SO FAR ---\n"
)


@dataclass
class TurnResult:
    player_input: str
    draft: str          # the runner's first draft
    final: str          # what reaches the player (== draft unless corrected)
    gate: "GateResult"  # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool


class Game:
    def __init__(self, backend, gate, runner_agent: str = "dm-runner",
                 on_turn=None, checks_log: str | None = None,
                 campaign_dir: str | None = None, session: int | None = None,
                 transcript: bool = True):
        self.backend = backend
        self.gate = gate
        self.runner_agent = runner_agent
        self.on_turn = on_turn
        self.checks_log = checks_log
        self.runner_sid = backend.create_session("dm-runner game")
        # The session being played = the highest plan on disk, unless told otherwise.
        self.campaign = Path(campaign_dir) if campaign_dir else Path(backend.directory) / "campaign"
        self.session = session if session is not None else _latest_session(self.campaign / "sessions")
        self.transcript_path = (
            self.campaign / "sessions" / f"session-{self.session}-transcript.md"
            if (transcript and self.session) else None
        )

    def start(self, kickoff: str = "Let's begin the session.") -> TurnResult:
        """The opening scene — gated like any turn (it's player-facing narration).
        Resets the transcript and records the opening narration (no player line).
        The runner opens with its prepared context (plan + canon) loaded in front of
        it, so it isn't relying on its own file reads to know the session."""
        self._init_transcript()
        opening = self._runner_preload() + kickoff
        tr = self._gated_turn(opening, kickoff, opening=True)
        self._save_runner_sid()  # so a later run can reattach this session
        return tr

    def resume(self) -> str | None:
        """Resume an in-progress session. Returns the scene to continue from (the last
        DM beat in the transcript), or None if there's nothing to resume — in which
        case the caller should `start()` instead.

        Two paths (chosen automatically): if the runner session from a prior run is
        still live on the server, **reattach** to it (its full context is intact);
        otherwise **rebuild** the context in a fresh session by priming it with the
        transcript. Either way the transcript file is appended to, never reset."""
        transcript = self._read_transcript()
        if not transcript.strip():
            return None
        saved = self._load_runner_sid()
        if saved and self.backend.session_valid(saved):
            self.runner_sid = saved                       # fast path: live session, context intact
        else:
            # durable path: a fresh session has neither the plan nor the play so far —
            # give it both (prepared context, then the transcript to continue from).
            prime = self._runner_preload() + _RESUME_PRIME + transcript
            self.backend.prompt(self.runner_sid, self.runner_agent, prime)
        self._save_runner_sid()
        return _last_dm_beat(transcript)

    def turn(self, player_input: str) -> TurnResult:
        # The per-turn craft reminder rides in front of the player's message — the
        # most salient slot, fresh every turn, so the algorithm (especially "ask for
        # a roll") doesn't decay over a long session. The gate and the transcript see
        # only the clean player_msg, never the reminder.
        message = f"{_TURN_REMINDER}\n\n--- PLAYER MESSAGE ---\n{player_input}"
        return self._gated_turn(message, player_input)

    def meta(self, question: str) -> str:
        """An out-of-game question. The runner answers it (spoiler-free, per its
        prompt); the orchestrator does NOT gate it — it isn't narration, and it
        never reaches the transcript."""
        return self.backend.prompt(self.runner_sid, self.runner_agent, question)

    def _gated_turn(self, message: str, player_msg: str, opening: bool = False) -> TurnResult:
        draft = self.backend.prompt(self.runner_sid, self.runner_agent, message)
        result = self.gate.check(draft, player_msg)
        final, corrected = draft, False
        if result.violations:
            # Exactly one correction pass. We do NOT re-gate the revision — bounded
            # by construction; if it's still imperfect it goes out and the log shows it.
            final = self.backend.prompt(self.runner_sid, self.runner_agent, result.correction_brief())
            corrected = True
        tr = TurnResult(player_msg, draft, final, result, corrected)
        self._append_transcript(player_msg, final, opening)  # the FINAL narration, never the draft
        self._log(tr)
        if self.on_turn:
            self.on_turn(tr)
        return tr

    # -- transcript (final messages only) -----------------------------------

    def _init_transcript(self) -> None:
        if not self.transcript_path:
            return
        try:
            self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            self.transcript_path.write_text(f"# Session {self.session} — transcript\n\n")
        except OSError:
            pass

    def _append_transcript(self, player_msg: str, final: str, opening: bool) -> None:
        if not self.transcript_path:
            return
        blocks = []
        if not opening:  # the opening has no player line — it's the runner's scene-set
            blocks += ["## Player", "", player_msg.strip(), ""]
        blocks += ["## DM", "", final.strip(), ""]
        try:
            with open(self.transcript_path, "a") as f:
                f.write("\n".join(blocks) + "\n")
        except OSError:
            pass

    def _read_transcript(self) -> str:
        if not self.transcript_path:
            return ""
        try:
            return self.transcript_path.read_text() if self.transcript_path.is_file() else ""
        except OSError:
            return ""

    def _runner_preload(self) -> str:
        """The runner's prepared context block (plan + canon), via the gate's
        preloader. Empty string if no preloader is wired (e.g. a mock gate) — the
        runner then falls back to reading the files itself per its prompt."""
        pre = getattr(self.gate, "preloader", None)
        if pre is None:
            return ""
        try:
            return pre.runner_preload(self.session)
        except Exception:
            return ""

    # -- session-id persistence (for resume reattach) -----------------------

    def _state_path(self) -> Path | None:
        """Where we stash the runner session id — under `.opencode/.orchestrator/`,
        which the campaign repo gitignores, so it never lands in a commit."""
        if not self.session:
            return None
        return Path(self.backend.directory) / ".opencode" / ".orchestrator" / f"session-{self.session}.json"

    def _save_runner_sid(self) -> None:
        p = self._state_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"runner_sid": self.runner_sid}))
        except OSError:
            pass

    def _load_runner_sid(self) -> str | None:
        p = self._state_path()
        if not p:
            return None
        try:
            return json.loads(p.read_text()).get("runner_sid")
        except (OSError, ValueError):
            return None

    def _log(self, tr: TurnResult) -> None:
        if not self.checks_log:
            return
        try:
            with open(self.checks_log, "a") as f:
                f.write(_format_block(tr))
        except OSError:
            pass


def _last_dm_beat(transcript: str) -> str:
    """The last `## DM` block in a transcript — the scene a resume continues from."""
    parts = re.split(r"(?m)^## (Player|DM)[ \t]*$", transcript)
    # re.split with one capture group yields [pre, label, body, label, body, ...]
    last = ""
    for i in range(1, len(parts) - 1, 2):
        if parts[i] == "DM":
            last = parts[i + 1].strip()
    return last


def _latest_session(sessions_dir: Path) -> int | None:
    """The session being played: the highest `session-{N}-plan.md` on disk."""
    n = 0
    try:
        for f in Path(sessions_dir).iterdir():
            m = re.match(r"session-(\d+)-plan\.md$", f.name)
            if m:
                n = max(n, int(m.group(1)))
    except OSError:
        return None
    return n or None


def _sec(label: str, body: str) -> str:
    return f"\n  ── {label} {'─' * max(0, 68 - len(label))}\n\n{(body or '').strip()}\n"


def _format_block(tr: TurnResult) -> str:
    bar = "█" * 74
    g = tr.gate
    blocks = [
        "", bar,
        f"  TURN  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
        f"{'CORRECTED' if tr.corrected else 'clean'}  ·  canon {g.canon_sections} sections",
        bar,
        _sec("PLAYER", tr.player_input),
        _sec(f"CANON · {g.narrative.label}", g.narrative.report),
        _sec(f"CONDUCT · {g.conduct.label}", g.conduct.report),
    ]
    if tr.corrected:
        blocks.append(_sec("DRAFT (pre-correction)", tr.draft))
    blocks.append(_sec("FINAL NARRATION", tr.final))
    blocks.append("")
    return "\n\n".join(blocks)
