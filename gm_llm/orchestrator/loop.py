"""
The per-turn loop.

The player's message goes to the DM (`dm-runner`) and the DM's reply goes to the player. Nothing
sits in between: no reminder rides in front of the message and no checker reviews the reply
(design/luna.md § Live play). Checks are the benchmark's business, after play, over the archive.

The orchestrator owns the **transcript**: it writes `campaign/sessions/<N>/transcript.md` from each
turn's player message and DM narration, and `log-extractor` reads that record after the session.

The DM ends a session by calling `task_complete` once, with its handoff notes in `notes`; its
closing narration is its reply text, shown to the player like any turn's. The closing narration
joins the transcript; the notes are filed to `sessions/<N>/notes.md`.

`Game` is the headless core. Interfaces (the TUI, the benchmark) drive it:
  g = Game(backend, preloader)
  g.start()                 # the DM opens the scene
  g.turn(player_input)      # one turn -> TurnResult
  g.meta(question)          # an out-of-game question, kept out of the transcript
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .backend import HEAVY_RETRIES, HEAVY_STALL_TIMEOUT, BackendCancelled, BackendError
from .combat import CombatMixin, CombatState
from .logs import append, banner, section
from .paths import latest_session
from .prompts import load

# A bare end-of-session trailer: a line whose ONLY content is a "session complete/ends here"
# marker, optionally wrapped in markdown emphasis or a rule. Matched against the narration's
# last non-empty line, so it can't fire on ordinary prose.
_CLOSE_MARKER = re.compile(
    r"^[\s>#*_~`-]*"
    r"(?:the\s+)?(?:end\s+of\s+(?:the\s+)?session"
    r"|session\s+(?:complete|over|ends?(?:\s+here)?)"
    r"|end\s+of\s+session)"
    r"[\s>#*_~`.!—-]*$",
    re.IGNORECASE,
)


def _looks_like_close(text: str) -> bool:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return bool(lines) and _CLOSE_MARKER.match(lines[-1]) is not None


def join_narration(text: str, closing: str) -> str:
    """The reply's own text plus a closing the code appends — either may be empty, and a
    model that repeats one inside the other gets it once."""
    text, closing = (text or "").strip(), (closing or "").strip()
    if not closing or closing in text:
        return text
    if not text or text in closing:
        return closing
    return f"{text}\n\n{closing}"


def strip_prologue(text: str, prologue: str) -> str:
    """The reply without a copy of the prologue it opens on (the code reads that out itself),
    however the copy is wrapped or tagged."""
    copy = r"\s+".join(map(re.escape, prologue.split()))
    m = re.match(rf"\s*(?:<prologue>\s*)?{copy}\s*(?:</prologue>)?", text or "")
    return (text[m.end():] if m else text or "").strip()


@dataclass
class TurnResult:
    player_input: str
    final: str                      # the DM's narration, as the player sees it
    session_complete: bool = False  # the DM signalled the session's end via task_complete
    combat_started: bool = False    # the DM called start_encounter this turn
    close_nudged: bool = False      # the reply ended in prose; a close nudge was dispatched
    tools: frozenset[str] = frozenset()  # every tool the DM called this turn
    rolls: tuple[str, ...] = ()     # the DM's dice calls this turn, "expression = total"


class Game(CombatMixin):
    def __init__(self, backend, preloader=None, runner_agent: str = "dm-runner",
                 on_turn=None, on_step=None, logs=None,
                 campaign_dir: str | None = None, session: int | None = None,
                 transcript: bool = True):
        self.backend = backend
        self.preloader = preloader
        self.runner_agent = runner_agent
        self.on_turn = on_turn
        self.on_step = on_step  # fires per turn-step ("draft"/"done")
        # Turn ordinal within THIS run (the archive's turn id). A resume starts a new run over
        # the same session — the archive's `resume` event marks the restart.
        self._turn_no = 0
        self.logs = logs
        self.runner_sid = backend.create_session("dm-runner game")
        # Combat mode (design/combat.md § The combat loop). `_in_combat` reflects a live tracker
        # state file, so a resume into a fight picks it up.
        self._in_combat = CombatState(backend.directory).exists()
        self._combat_pending = None
        # The session being played = the highest plan on disk, unless told otherwise.
        self.campaign = Path(campaign_dir) if campaign_dir else Path(backend.directory) / "campaign"
        self.session = session if session is not None else latest_session(self.campaign)
        self.transcript_path = (paths.transcript(self.campaign, self.session)
                                if (transcript and self.session) else None)

    def start(self, kickoff: str = "Let's begin the session.") -> TurnResult:
        """The opening scene. Resets the transcript and records the opening narration (no
        player line). The DM opens with its prepared context in front of it. A session with a
        prologue (the first) leads with it, read out verbatim, and the DM opens where it ends."""
        self._init_transcript()
        prologue = self._read_prologue()
        lead = load("runner-prologue").format(prologue=prologue) + "\n\n" if prologue else ""
        tr = self._play(self._runner_preload() + lead + kickoff, kickoff, opening=True,
                        prologue=prologue)
        self._save_runner_sid()  # so a later run can reattach this session
        return tr

    def resume(self) -> str | None:
        """Resume an in-progress session. Returns the scene to continue from (the last DM beat
        in the transcript), or None if there's nothing to resume — the caller then `start()`s.

        If the DM's session from a prior run is still live on the server, **reattach** to it;
        otherwise **rebuild** the context in a fresh session from the prepared context and the
        transcript. Either way the transcript is appended to, never reset."""
        transcript = self._read_transcript()
        scene = _last_dm_beat(transcript)
        if not scene:  # nothing played yet — a quit before the opening landed leaves a bare title
            return None
        saved = self._load_runner_sid()
        if saved and self.backend.session_valid(saved):
            self.runner_sid = saved
        else:
            prime = (self._runner_preload() + load("resume-prime")
                     + "\n\n<play-so-far>\n" + transcript + "\n</play-so-far>")
            self.backend.prompt(self.runner_sid, self.runner_agent, prime)
        self._save_runner_sid()
        if self.logs and self.logs.archive:
            self.logs.archive.emit("resume", session=self.session)
        return scene

    def turn(self, player_input: str) -> TurnResult:
        """One turn. The player's words are fenced in <player>…</player> so the DM never
        mistakes an orchestrator message for the player's fiction, or the reverse."""
        return self._play(f"<player>\n{player_input}\n</player>", player_input)

    def context_usage(self):
        """The DM session's live context footprint — best-effort, None if unavailable."""
        return self.backend.context_usage(self.runner_sid)

    def meta(self, question: str) -> str:
        """An out-of-game question. Answered by the DM, kept out of the transcript."""
        return self.backend.prompt(self.runner_sid, self.runner_agent, question)

    def handoff(self) -> Path | None:
        """Make sure the session's handoff notes are on disk. They normally arrived with the
        closing `task_complete`; if they didn't, ask the still-warm DM for them once (the
        `handoff-brief`). Idempotent and best-effort — a failure never blocks the wrap."""
        if not self.session:
            return None
        notes_path = paths.notes(self.campaign, self.session)
        if notes_path.is_file():
            return notes_path
        try:
            with self.backend.patient(HEAVY_STALL_TIMEOUT, retries=HEAVY_RETRIES):
                reply = self.backend.prompt_full(self.runner_sid, self.runner_agent,
                                                 load("handoff-brief"))
                reply = self.backend.ensure_tool(self.runner_sid, self.runner_agent, reply,
                                                 tool="task_complete", args=("notes",),
                                                 nudge=load("nudge-notes"))
        except BackendCancelled:
            raise
        except BackendError:
            return None
        notes = (reply.tool_inputs.get("task_complete", {}).get("notes") or "").strip()
        return self._write_notes(notes or reply.text.strip())

    def abort(self) -> bool:
        """Cancel the model call in flight (the UI's cancel key). The blocked call raises
        `BackendCancelled` before the transcript is touched, so a cancelled turn leaves no
        trace. Returns True if there was a live call to cancel."""
        return self.backend.abort()

    def revert_last_turn(self) -> bool:
        """After a cancel, roll the DM session back over the abandoned turn."""
        return self.backend.revert_exchange(self.runner_sid)

    def _step(self, key: str) -> None:
        """Announce a turn-step to a watcher (the engine's busy label). Never raises."""
        if self.on_step:
            try:
                self.on_step(key)
            except Exception:  # noqa: BLE001 — the watcher is best-effort by design
                pass

    def _play(self, message: str, player_msg: str, opening: bool = False,
              prologue: str = "") -> TurnResult:
        self._turn_no += 1
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, message)
        narration = reply.text  # the nudge's reply below only supplies the missing call
        rolls = reply.rolls
        close_nudged = False
        if not opening and "task_complete" not in reply.tools and _looks_like_close(reply.text):
            reply = self.backend.ensure_tool(self.runner_sid, self.runner_agent, reply,
                                             tool="task_complete", nudge=load("nudge-close"))
            close_nudged = True
        session_complete = (not opening) and ("task_complete" in reply.tools)
        if session_complete:
            closing = reply.tool_inputs.get("task_complete", {})
            self._write_notes((closing.get("notes") or "").strip())
            # A disk fact, so a wrap the player never confirms still shows the same choice
            # after a restart instead of resuming into more play.
            self._mark_complete()
        if prologue:  # read out ahead of the opening scene, in the transcript as in the reply
            narration = join_narration(prologue, strip_prologue(narration, prologue))
        self._step("done")
        self._combat_observe(reply)
        tr = TurnResult(player_msg, narration, session_complete,
                        combat_started=("start_encounter" in reply.tools),
                        close_nudged=close_nudged, tools=frozenset(reply.tools), rolls=rolls)
        self._append_transcript(player_msg, narration, opening)
        self._log(tr)
        self._archive_turn(tr, opening)
        if self.on_turn:
            self.on_turn(tr)
        return tr

    def _write_notes(self, notes: str) -> Path | None:
        if not (notes and self.session):
            return None
        notes_path = paths.notes(self.campaign, self.session)
        try:
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(f"# Session {self.session} — DM handoff notes\n\n{notes}\n",
                                  encoding="utf-8")
        except (OSError, ValueError):
            return None
        return notes_path

    # -- transcript -----------------------------------------------------------

    def _init_transcript(self) -> None:
        if not self.transcript_path:
            return
        try:
            self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            self.transcript_path.write_text(f"# Session {self.session} — transcript\n\n",
                                            encoding="utf-8")
        except (OSError, ValueError):
            pass

    def _append_transcript(self, player_msg: str, narration: str, opening: bool,
                           dm_only: bool = False) -> None:
        if not self.transcript_path:
            return
        blocks = []
        # No player line for the opening scene-set or an NPC combat beat (dm_only).
        if not opening and not dm_only:
            blocks += ["## Player", "", player_msg.strip(), ""]
        blocks += ["## DM", "", narration.strip(), ""]
        try:
            with open(self.transcript_path, "a", encoding="utf-8") as f:
                f.write("\n".join(blocks) + "\n")
        except (OSError, ValueError):
            pass

    def _read_prologue(self) -> str:
        p = paths.prologue(self.campaign, self.session) if self.session else None
        try:
            return p.read_text(encoding="utf-8").strip() if p and p.is_file() else ""
        except OSError:
            return ""

    def _read_transcript(self) -> str:
        if not self.transcript_path:
            return ""
        try:
            return (self.transcript_path.read_text(encoding="utf-8")
                    if self.transcript_path.is_file() else "")
        except (OSError, ValueError):
            return ""

    def _runner_preload(self) -> str:
        """The DM's prepared context block (plan + canon), or '' with no preloader wired —
        the DM then reads the files itself."""
        if self.preloader is None:
            return ""
        try:
            return self.preloader.runner_preload(self.session)
        except Exception:
            return ""

    # -- session-id persistence (for resume reattach) -------------------------

    def _state_path(self) -> Path | None:
        """Where the DM session id is kept — under `.opencode/.orchestrator/`, which the
        campaign repo ignores."""
        if not self.session:
            return None
        return _session_state_path(self.backend.directory, self.session)

    def _save_runner_sid(self) -> None:
        p = self._state_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"runner_sid": self.runner_sid}), encoding="utf-8")
        except (OSError, ValueError):
            pass

    def _load_runner_sid(self) -> str | None:
        p = self._state_path()
        if not p:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("runner_sid")
        except (OSError, ValueError):
            return None

    def _mark_complete(self) -> None:
        """Persist that the DM signalled the end, so `Lifecycle` sees it on the next launch."""
        p = self._state_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"runner_sid": self.runner_sid, "complete": True}),
                         encoding="utf-8")
        except (OSError, ValueError):
            pass

    # -- logs and archive -------------------------------------------------------

    def _log(self, tr: TurnResult) -> None:
        if self.logs:
            append(self.logs.checks, _format_block(tr))

    def _archive_turn(self, tr: TurnResult, opening: bool, **extra) -> None:
        """One `turn` event: what the player said, what the DM narrated, which tools it
        called, and the context size — everything the after-play checker reads."""
        if not (self.logs and self.logs.archive):
            return
        cu = self.backend.context_usage(self.runner_sid)
        self.logs.archive.emit(
            "turn", session=self.session, turn=self._turn_no, opening=opening,
            player=tr.player_input, narration=tr.final,
            session_complete=tr.session_complete, close_nudged=tr.close_nudged,
            tools=sorted(tr.tools), rolls=list(tr.rolls),
            context=({"tokens": cu.tokens, "limit": cu.context_limit} if cu else None),
            **extra,
        )


def _session_state_path(directory: str, n: int) -> Path:
    return Path(directory) / ".opencode" / ".orchestrator" / f"session-{n}.json"


def session_is_complete(directory: str, n: int) -> bool:
    """Whether session `n`'s DM already signalled the end via `task_complete` — read off
    disk, no model call."""
    try:
        data = json.loads(_session_state_path(directory, n).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(data.get("complete"))


def _last_dm_beat(transcript: str) -> str:
    """The last `## DM` block in a transcript — the scene a resume continues from."""
    parts = re.split(r"(?m)^## (Player|DM)[ \t]*$", transcript)
    last = ""
    for i in range(1, len(parts) - 1, 2):
        if parts[i] == "DM":
            last = parts[i + 1].strip()
    return last


def _format_block(tr: TurnResult) -> str:
    tools = ", ".join(sorted(tr.tools)) or "none"
    return "\n\n".join([
        banner(f"TURN  ·  tools: {tools}"
               + ("  ·  SESSION COMPLETE" if tr.session_complete else "")),
        section("PLAYER", tr.player_input),
        section("DM", tr.final),
        "",
    ])
