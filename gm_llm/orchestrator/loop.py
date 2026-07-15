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

from .backend import BackendCancelled, BackendError
from .canon import latest_session
from .logs import append, banner, section
from .prompts import load

# Safety-hatch nudge: sent if the runner wrote its handoff notes as prose instead of
# delivering them in task_complete's `notes` arg (the only channel the orchestrator
# files — same pattern as setup's world overview).
_NUDGE_NOTES = (
    "You wrote the handoff notes but didn't deliver them — the `notes` argument of "
    "`task_complete` is the only channel the orchestrator files; a prose reply is not "
    "captured. Call `task_complete` now with the complete notes in `notes`."
)


@dataclass
class TurnResult:
    player_input: str
    draft: str          # the runner's first draft
    final: str          # what reaches the player (== draft unless corrected)
    gate: "GateResult"  # noqa: F821 — annotation only (lazy via __future__)
    corrected: bool
    session_complete: bool = False  # the runner signalled the session's end via task_complete


class Game:
    def __init__(self, backend, gate, runner_agent: str = "dm-runner",
                 on_turn=None, on_step=None, logs=None,
                 campaign_dir: str | None = None, session: int | None = None,
                 transcript: bool = True):
        self.backend = backend
        self.gate = gate
        self.runner_agent = runner_agent
        self.on_turn = on_turn
        self.on_step = on_step  # fires per turn-step ("draft"/"check"/"correct"/"done")
        # True only while the (single, bounded) correction prompt is in flight — left
        # set if that prompt is cancelled, so revert_last_turn knows to roll back past
        # the correction brief to the player's own message. Reset at the next op.
        self._correcting = False
        self.logs = logs
        self.runner_sid = backend.create_session("dm-runner game")
        # The session being played = the highest plan on disk, unless told otherwise.
        self.campaign = Path(campaign_dir) if campaign_dir else Path(backend.directory) / "campaign"
        self.session = session if session is not None else latest_session(self.campaign / "sessions")
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
            # give it both (prepared context, then the transcript to continue from). The
            # transcript is fenced in <play-so-far>…</play-so-far> so the runner reads it
            # as the established record to absorb, not a scene to re-narrate.
            prime = (self._runner_preload() + load("resume-prime")
                     + "\n\n<play-so-far>\n" + transcript + "\n</play-so-far>")
            self.backend.prompt(self.runner_sid, self.runner_agent, prime)
        self._save_runner_sid()
        return _last_dm_beat(transcript)

    def turn(self, player_input: str) -> TurnResult:
        # The per-turn craft reminder rides in front of the player's message — the
        # most salient slot, fresh every turn, so the algorithm (especially "ask for
        # a roll") doesn't decay over a long session. The player's own words are fenced
        # in <player>…</player> so the runner never mistakes an orchestrator instruction
        # for the player's fiction (or vice versa). The gate and the transcript see only
        # the clean player_msg, never the reminder or the fence.
        message = f"{load('turn-reminder')}\n\n<player>\n{player_input}\n</player>"
        return self._gated_turn(message, player_input)

    def context_usage(self):
        """The runner session's live context footprint — see
        `Backend.context_usage`. Best-effort; `None` if the lookup fails (a
        status-only signal, never worth failing a turn over)."""
        return self.backend.context_usage(self.runner_sid)

    def meta(self, question: str) -> str:
        """An out-of-game question. The runner answers it (spoiler-free, per its
        prompt); the orchestrator does NOT gate it — it isn't narration, and it
        never reaches the transcript."""
        self._correcting = False
        return self.backend.prompt(self.runner_sid, self.runner_agent, question)

    def handoff(self) -> Path | None:
        """At session end, ask the still-live runner (its context warm from the whole
        session) for its handoff notes — story-trajectory changes, new/changed entities,
        threads touched — and write them to `campaign/sessions/session-{N}-notes.md`, which
        the between-session pipeline folds in alongside the transcript.

        The notes ride in `task_complete`'s `notes` argument (the same delivery as the
        world overview at setup): a structured field code reads from the tool call, never
        prose fished out of the reply, which text-part splits and trailing closers have
        made unreliable. The reply text stays as a fallback for a runner that wrote the
        notes but skipped the call even after the nudge.

        Ungated (internal notes, not player-facing narration; never hits the transcript).
        The runner has no write permission, so the orchestrator writes the file itself.
        Idempotent: no-ops if the notes already exist, so a re-run/resume of the wrap
        doesn't re-dispatch. Best-effort — a failure never blocks the wrap."""
        if not self.session:
            return None
        notes_path = self.campaign / "sessions" / f"session-{self.session}-notes.md"
        if notes_path.is_file():
            return notes_path
        self._correcting = False
        try:
            reply = self.backend.prompt_full(self.runner_sid, self.runner_agent,
                                             load("handoff-brief"), whole=True)
            reply = self.backend.ensure_tool(self.runner_sid, self.runner_agent, reply,
                                             tool="task_complete", args=("notes",),
                                             nudge=_NUDGE_NOTES, whole=True)
        except BackendCancelled:
            raise  # the player cancelled — unwind the wrap, don't paper over it
        except BackendError:
            return None  # notes are optional — the pipeline proceeds without them
        notes = (reply.tool_inputs.get("task_complete", {}).get("notes") or "").strip()
        notes = notes or reply.text.strip()
        if not notes:
            return None
        try:
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(
                f"# Session {self.session} — runner handoff notes\n\n{notes.strip()}\n",
                encoding="utf-8")
        except (OSError, ValueError):
            return None
        return notes_path

    def abort(self) -> bool:
        """Cancel the model call in flight for the current turn (the UI's cancel
        key, e.g. after a mistype). The blocked `start`/`turn`/`meta` raises
        `BackendCancelled`, which unwinds before `_gated_turn` reaches the
        transcript append — so a cancelled turn leaves no trace in canon or state.
        Returns True if there was a live call to cancel."""
        return self.backend.abort()

    def revert_last_turn(self) -> bool:
        """After a cancel, roll the runner session back over the abandoned turn (see
        Backend.revert_to_recent_user). The transcript and state were never touched
        (the cancel raised before they were written); this just clears the turn's
        messages from the runner's own context so the next turn continues clean. Call
        once the cancelled call has unwound.

        Reverts to the player's own message — `back=2` if the cancel landed in the
        correction pass (reaching past the correction brief), else `back=1`. Either
        way the whole turn goes, never a half (the correction is bounded to one pass,
        so a turn adds at most two user messages)."""
        return self.backend.revert_to_recent_user(self.runner_sid, back=2 if self._correcting else 1)

    def _step(self, key: str) -> None:
        """Announce a turn-step to a watcher (the TUI status bar). Never raises —
        a UI failure must not break the turn (same contract as Setup._announce)."""
        if self.on_step:
            try:
                self.on_step(key)
            except Exception:  # noqa: BLE001 — the watcher is best-effort by design
                pass

    def _gated_turn(self, message: str, player_msg: str, opening: bool = False) -> TurnResult:
        self._correcting = False
        self._step("draft")
        reply = self.backend.prompt_full(self.runner_sid, self.runner_agent, message)
        draft = reply.text
        # The runner ends a session by calling `task_complete` as its final act (after its
        # closing beats). We read that off the draft's tool calls — never the opening, which
        # is a scene-set, not an ending.
        session_complete = (not opening) and ("task_complete" in reply.tools)
        if session_complete:
            # A disk fact, not just this TurnResult — so a wrap the player never
            # confirms still shows the same choice after a restart instead of
            # quietly resuming into more play (see `session_is_complete`).
            self._mark_complete()
        self._step("check")
        result = self.gate.check(draft, player_msg)
        final, corrected = draft, False
        if result.violations:
            # Exactly one correction pass. We do NOT re-gate the revision — bounded
            # by construction; if it's still imperfect it goes out and the log shows it.
            # _correcting brackets the correction prompt: if it's cancelled it stays
            # set, so revert_last_turn rolls back past the brief to the player message.
            self._correcting = True
            self._step("correct")
            final = self.backend.prompt(self.runner_sid, self.runner_agent, result.correction_brief())
            self._correcting = False
            corrected = True
        self._step("done")
        tr = TurnResult(player_msg, draft, final, result, corrected, session_complete)
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
            self.transcript_path.write_text(f"# Session {self.session} — transcript\n\n",
                                            encoding="utf-8")
        except (OSError, ValueError):
            pass

    def _append_transcript(self, player_msg: str, final: str, opening: bool) -> None:
        if not self.transcript_path:
            return
        blocks = []
        if not opening:  # the opening has no player line — it's the runner's scene-set
            blocks += ["## Player", "", player_msg.strip(), ""]
        blocks += ["## DM", "", final.strip(), ""]
        try:
            with open(self.transcript_path, "a", encoding="utf-8") as f:
                f.write("\n".join(blocks) + "\n")
        except (OSError, ValueError):
            pass

    def _read_transcript(self) -> str:
        if not self.transcript_path:
            return ""
        try:
            return (self.transcript_path.read_text(encoding="utf-8")
                    if self.transcript_path.is_file() else "")
        except (OSError, ValueError):
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
        """Persist that this session's runner has signalled the end (`task_complete`
        fired) as a disk fact, not just this call's TurnResult — so `Lifecycle` can
        see it on the next launch too, before ever touching the model, and show the
        same wrap-or-quit choice again instead of quietly resuming into more play."""
        p = self._state_path()
        if not p:
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"runner_sid": self.runner_sid, "complete": True}),
                        encoding="utf-8")
        except (OSError, ValueError):
            pass

    def _log(self, tr: TurnResult) -> None:
        if self.logs:
            append(self.logs.checks, _format_block(tr))


def _session_state_path(directory: str, n: int) -> Path:
    return Path(directory) / ".opencode" / ".orchestrator" / f"session-{n}.json"


def session_is_complete(directory: str, n: int) -> bool:
    """Whether session `n`'s runner already signalled the end via `task_complete` —
    read straight off disk, no model call. `Lifecycle` checks this before deciding
    whether to resume play or show the wrap-or-quit choice again, so a session the
    player closed the app on without confirming the wrap can't be resumed into more
    play on the next launch."""
    try:
        data = json.loads(_session_state_path(directory, n).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(data.get("complete"))


def _last_dm_beat(transcript: str) -> str:
    """The last `## DM` block in a transcript — the scene a resume continues from."""
    parts = re.split(r"(?m)^## (Player|DM)[ \t]*$", transcript)
    # re.split with one capture group yields [pre, label, body, label, body, ...]
    last = ""
    for i in range(1, len(parts) - 1, 2):
        if parts[i] == "DM":
            last = parts[i + 1].strip()
    return last


def _format_block(tr: TurnResult) -> str:
    g = tr.gate
    blocks = [
        banner(f"TURN  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
               f"{'CORRECTED' if tr.corrected else 'clean'}  ·  canon {g.canon_sections} sections"),
        section("PLAYER", tr.player_input),
        section(f"CANON · {g.narrative.label}", g.narrative.report),
        section(f"CONDUCT · {g.conduct.label}", g.conduct.report),
    ]
    if tr.corrected:
        blocks.append(section("DRAFT (pre-correction)", tr.draft))
    blocks.append(section("FINAL NARRATION", tr.final))
    blocks.append("")
    return "\n\n".join(blocks)
