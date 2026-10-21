"""
PlayApp — the Textual frontend, a client of the engine (design/frontends.md).

The app renders the engine's events and sends it commands; it decides nothing about play.
What a line of input is taken as, which commands are on offer, when a session can wrap —
all of that arrives in `state` events, and the app greys out what `actions` doesn't list.

Layout: a scene pane (DM narration and your lines, one selectable block per beat), a
behind-the-screen pane (the live model stream and a tool summary per turn), a status bar
(what the table is doing, with an elapsed clock), a prompt bar (yes/no at a phase
boundary) and an input that switches between ACTION mode (a turn) and META mode (an
out-of-game question). The input stays live while the table works, so the next message can
be drafted; sending waits until the engine asks for it.

Events arrive on a client queue, read by one worker thread that hops each onto the UI
thread. A batch (`hello` with `batch: true`) is watched, not played: the engine offers no
input, and the header tallies run *k* of *N*.
"""

from __future__ import annotations

import queue
from types import SimpleNamespace

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, RichLog

from gm_llm.dice import roll_expr

from .markup import StreamRenderer, inline
from .screens import MenuScreen, RollScreen, StatusScreen
from .widgets import (
    BatchHeader, DMBlock, PendingBlock, PlayerLine, PromptBar, SceneLine, StatusBar,
)

_ASK = {
    "setup_done": "Setup complete — plan & start session 1?",
    "ready": "Session {n} planned — start playing it now?",
    "complete": "Session {n} complete — reconcile & prep session {next}?",
}


class PlayApp(App):
    CSS = """
    #main   { height: 1fr; }
    #scene  { width: 2fr; border: round $primary;   padding: 0 1; }
    #screen { width: 1fr; border: round $secondary; }
    #screen.hidden { display: none; }
    #cmd { height: 3; border: tall $accent; }
    """

    BINDINGS = [
        ("escape", "menu", "Menu"),
        ("ctrl+g", "toggle_screen", "Behind-screen"),
        ("ctrl+t", "toggle_mode", "Action/Meta"),
        # priority: the input keeps focus while the table works (drafting), and
        # Input binds ctrl+x (cut) / ctrl+w (delete word) itself — these must
        # reach the app regardless.
        Binding("ctrl+x", "cancel", "Cancel turn", priority=True),
        Binding("ctrl+w", "wrap", "Wrap session", priority=True),
        ("ctrl+q", "quit", "Quit"),
    ]

    # Cap the scene pane's mounted blocks so layout stays cheap as the session grows. The
    # full transcript is always on disk — this is just the visible scrollback.
    _SCENE_MAX_BLOCKS = 200

    def __init__(self, client, theme: str = "dracula"):
        super().__init__()
        self.client = client
        self._theme = theme
        self.mode = "action"
        self.state: dict = {"phase": "starting", "actions": []}
        self.batch = False
        self.batch_records: list[dict] = []
        self._thinking = None        # the PendingBlock in the scene while the table works
        self._ctx_note = ""          # " · ctx 39% (78k/200k)"
        self._stream = StreamRenderer()

    # -- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield BatchHeader()
        with Horizontal(id="main"):
            yield VerticalScroll(id="scene")
            # RichLog: append-efficient, scrolls itself, parses console markup. Not
            # text-selectable — the full logs are on disk under the project's
            # .opencode/logs/. min_width=0 lets it wrap at the pane's real width.
            yield RichLog(id="screen", markup=True, wrap=True, auto_scroll=False,
                          min_width=0, classes="hidden")
        yield StatusBar()
        yield PromptBar()
        yield Input(id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = self._theme if self._theme in self.available_themes else "dracula"
        self._status = self.query_one(StatusBar)
        self._prompt = self.query_one(PromptBar)
        self._header = self.query_one(BatchHeader)
        self._write_screen("[b]behind the screen[/b] — live model stream · tools per turn")
        self._sync_input()
        self.run_worker(self._pump, thread=True, group="pump")

    def _pump(self) -> None:
        """Hand each engine event to the UI thread, until the engine closes or the app
        stops. `call_from_thread` would park on a stopped app, so check first."""
        while self.is_running:
            try:
                ev = self.client.events.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.call_from_thread(self._on_event, ev)
            except RuntimeError:
                return  # the app stopped between the check and the call
            if ev["type"] == "state" and ev["phase"] == "closed":
                return

    # -- events --------------------------------------------------------------

    def _on_event(self, ev: dict) -> None:
        handler = getattr(self, f"_ev_{ev['type']}", None)
        if handler:
            handler(ev)

    def _ev_hello(self, ev: dict) -> None:
        self.batch = ev.get("batch", False)
        if self.batch:
            self._header.activate()
            self._scene_status("esc menu · ctrl+g behind-screen · ctrl+x cancel the call "
                               "in flight · ctrl+q stop the batch")
        else:
            self._scene_status("esc menu · ctrl+t action/meta · ctrl+g behind-screen · "
                               "ctrl+x cancel · ctrl+w wrap · /roll 2d6+3 · /meta <q> · /quit")

    def _ev_state(self, ev: dict) -> None:
        old, self.state = self.state, ev
        if ev["busy"] != old.get("busy"):
            if ev["busy"] is None:
                self._status.stop()
                self.query_one("#cmd", Input).focus()
            elif old.get("busy") is None:
                self._status.start(ev["busy"])
            else:
                self._status.set_phase(ev["busy"])
        self._sync_thinking()
        if ev["phase"] in _ASK and "advance" in ev["actions"]:
            if self._prompt.active:
                return self._sync_input()
            n = ev.get("session") or 0
            self._prompt.ask(_ASK[ev["phase"]].format(n=n, next=n + 1))
        elif self._prompt.active:
            self._prompt.dismiss()
        if ev["phase"] == "closed":
            self._scene_status("— the engine has stopped — ctrl+q to close —", kind="rule")
        self._sync_input()
        self._refresh_subtitle()

    def _ev_say(self, ev: dict) -> None:
        text, meta = ev["text"], ev.get("meta", False)
        if ev["speaker"] == "player":
            who = "Player" if self.state.get("player") == "auto" else "You"
            label = f"{who} (out-of-game)" if meta else f"[$success bold]{who}[/]"
            self._scene_mount(PlayerLine(f"{label}  {escape(text)}", meta=meta))
            return
        if ev.get("combatant"):
            self._scene_status(f"  ⚔ {'You' if ev['combatant'] == 'pc' else ev['combatant']}")
        self._scene_mount(DMBlock(inline(text), meta=meta))

    def _ev_notice(self, ev: dict) -> None:
        kind = ev["kind"]
        self._scene_status(f"— {ev['text']} —" if kind != "status" else ev["text"], kind=kind)

    def _ev_stage(self, ev: dict) -> None:
        self._scene_status(f"  ▸ {ev['label']}…")

    def _ev_progress(self, ev: dict) -> None:
        self._scene_status(f"  ▸ {ev['label']}…")

    def _ev_stream(self, ev: dict) -> None:
        self._append_screen(self._stream.feed(ev["kind"], ev["text"]))

    def _ev_turn(self, ev: dict) -> None:
        self._append_screen(self._stream.flush())
        tools = ", ".join(ev["tools"]) or "none"
        self._write_screen(f"\n[b]turn {ev['n']}[/b]  tools: {tools}")

    def _ev_context(self, ev: dict) -> None:
        # The denominator is the full window, so the readout stays under 100%.
        self._ctx_note = f" · ctx {ev['pct']:.0f}% ({ev['tokens'] / 1000:.0f}k/{ev['limit'] / 1000:.0f}k)"
        self._refresh_subtitle()

    def _ev_retry(self, ev: dict) -> None:
        # Sticky, with the running clock, so a rate-limited call stays visibly flagged the
        # whole time it retries. It clears when the next phase arrives.
        self._status.note(f"{ev['agent']} call failed ({escape(ev['reason'])}) — retry "
                          f"{ev['attempt']}/{ev.get('of') or '?'} in {ev['wait']}s", True)

    def _ev_handback(self, ev: dict) -> None:
        """A cancelled message comes back — into the box if it's empty, else as a note."""
        inp = self.query_one("#cmd", Input)
        if inp.value.strip():
            self._scene_status(f'— cancelled — your message was: "{escape(ev["text"])}" —',
                               kind="rule")
        else:
            inp.value = ev["text"]
            inp.cursor_position = len(ev["text"])
            self._scene_status("— cancelled — your message is back in the box —", kind="rule")

    def _ev_status(self, ev: dict) -> None:
        self.push_screen(StatusScreen(SimpleNamespace(**ev)))

    def _ev_error(self, ev: dict) -> None:
        self._scene_status(f"— {escape(ev['what'])} failed: {escape(ev['message'])} —",
                           kind="error")

    def _ev_batch(self, ev: dict) -> None:
        if ev["event"] == "run":
            self._header.set_run(ev["index"], ev["total"], ev["run"])
            self._scene_status(f"── run {ev['index']}/{ev['total']} · {ev['run']} ──",
                               kind="rule")
        elif ev["event"] == "close":
            self.batch_records.append(ev["record"])
            outcome = str(ev["record"].get("outcome", "?"))
            self._header.set_outcome(outcome)
            self._scene_status(f"— {ev['record'].get('run', 'run')}: {outcome} "
                               f"({ev['record'].get('turns', 0)} turn(s)) —",
                               kind="success" if outcome == "complete" else "error")
        else:
            self._header.set_done()
            self._scene_status("— the batch is done — ctrl+q to close —", kind="success")

    # -- scene pane (one widget per beat) ------------------------------------

    def _scene_mount(self, widget) -> None:
        """Mount a block, trim past the cap, keep the pending block last, and auto-follow
        only when pinned to the bottom — a reader scrolled up isn't yanked down."""
        scene = self.query_one("#scene", VerticalScroll)
        pinned = scene.scroll_offset.y >= scene.max_scroll_y - 2
        scene.mount(widget, before=self._thinking) if self._thinking else scene.mount(widget)
        blocks = [w for w in scene.children if not w.has_class("truncated")]
        excess = len(blocks) - self._SCENE_MAX_BLOCKS
        if excess > 0:
            for w in blocks[:excess]:
                w.remove()
            if not scene.query(".truncated"):
                scene.mount(SceneLine("… older beats truncated — full transcript in "
                                      "campaign/sessions/ …", classes="truncated"),
                            before=0)
        if pinned:
            # scroll after the mount has laid out, or max_scroll_y is stale
            self.call_after_refresh(lambda: scene.scroll_end(animate=False))

    def _scene_status(self, text: str, kind: str = "status") -> None:
        self._scene_mount(SceneLine(text, kind=kind))

    def _sync_thinking(self) -> None:
        """A pending block sits at the bottom of the scene while a model call is in flight."""
        busy = self.state.get("busy")
        if busy and self.state["phase"] in ("setup", "play"):
            if self._thinking is None:
                block = PendingBlock(busy)
                self._scene_mount(block)
                self._thinking = block
        elif self._thinking is not None:
            self._thinking.remove()
            self._thinking = None

    # -- behind-the-screen pane ----------------------------------------------

    def _write_screen(self, markup: str) -> None:
        self._append_screen(markup + "\n")

    def _append_screen(self, text: str) -> None:
        if not text:
            return
        log = self.query_one("#screen", RichLog)
        follow = log.scroll_offset.y >= log.max_scroll_y - 2
        log.write(text, scroll_end=follow)

    # -- input -----------------------------------------------------------------

    def _sync_input(self) -> None:
        inp = self.query_one("#cmd", Input)
        st = self.state
        awaiting, phase = st.get("awaiting"), st.get("phase")
        if self.batch:
            inp.border_title = "WATCHING — a bench batch plays itself"
            inp.placeholder = "nothing typed reaches the run · ctrl+q stops the batch"
        elif awaiting == "confirm":
            inp.border_title = "COMBAT — Enter to confirm, or type a reaction"
            inp.placeholder = "Enter to confirm the enemy's action · type a reaction to interject"
        elif awaiting == "pc_action":
            inp.border_title = "COMBAT — your turn"
            inp.placeholder = "What does your character do this turn?"
        elif st.get("busy"):
            inp.border_title = "…thinking — draft freely, send once the table frees up…"
        elif awaiting == "answer":
            inp.border_title = "SETUP — talk to the DM"
            inp.placeholder = "Answer the DM…"
        elif phase in _ASK:
            inp.border_title = "Y to go on, N not yet — or /quit"
            inp.placeholder = ""
        elif self.mode == "action":
            inp.border_title = "ACTION"
            inp.placeholder = "What does your character do?"
        else:
            inp.border_title = "META — out-of-game"
            inp.placeholder = "Ask the DM a logistical question…"

    def _refresh_subtitle(self) -> None:
        if self.batch:
            self.sub_title = "WATCHING"
        elif self.state.get("phase") in ("setup", "setup_done", "planning"):
            self.sub_title = "SETUP"
        else:
            self.sub_title = f"{self.mode.upper()} mode{self._ctx_note}"

    def _send(self, type_: str, text: str | None = None) -> None:
        self.client.send({"type": type_} if text is None else {"type": type_, "text": text})

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd":
            return  # a modal's input (the roll prompt), not the play bar
        text = event.value.strip()
        low = text.lower()
        acts = self.state.get("actions", [])
        awaiting = self.state.get("awaiting")
        if low in ("/quit", "/exit", "/q"):
            self.exit()
            return
        if low.startswith("/roll"):
            event.input.value = ""
            self._scene_status(roll_expr(text[5:].strip()) or "could not parse — try /roll 2d6+3",
                               kind="rule")
            return
        if awaiting == "confirm":  # a bare Enter confirms
            event.input.value = ""
            self._send("input", text)
            return
        if not text:
            return
        if self.batch:
            event.input.value = ""
            self._scene_status("— watching a bench batch — nothing typed reaches the run · "
                               "ctrl+q stops the batch —", kind="rule")
            return
        if self.state.get("busy") and "input" not in acts:
            self.notify("still thinking — your draft will keep", severity="warning", timeout=3)
            return
        if low in ("/wrap", "/end"):
            event.input.value = ""
            self.action_wrap()
            return
        if not awaiting:
            self._scene_status("— answer Y/N above, or /quit — nothing else reaches the table "
                               "until then —", kind="rule")
            return
        event.input.value = ""
        self._prompt.dismiss()
        if awaiting == "turn" and (low.startswith("/meta") or self.mode == "meta"):
            question = text[5:].strip() if low.startswith("/meta") else text
            if question:
                self._send("meta", question)
            return
        self._send("input", text)

    # -- actions ---------------------------------------------------------------

    def on_prompt_bar_answered(self, event: PromptBar.Answered) -> None:
        if event.value:
            self.action_wrap()
        else:
            self._scene_status("— not yet — go on anytime with ctrl+w or the esc menu —")

    def action_wrap(self) -> None:
        """The pending phase step — plan session 1, open the planned session, or wrap."""
        if self.batch:
            self.notify("a bench run wraps itself — ctrl+q stops the batch",
                        severity="warning", timeout=3)
        elif "advance" in self.state.get("actions", []):
            self._prompt.dismiss()
            self._send("advance")
        elif self.state.get("in_combat"):
            self.notify("finish the fight first — the session can't wrap mid-combat",
                        severity="warning", timeout=3)

    def action_cancel(self) -> None:
        if "cancel" in self.state.get("actions", []):
            self._send("cancel")

    def action_menu(self) -> None:
        """The mouse-and-arrow surface over the same actions the keybinds drive."""
        if isinstance(self.screen, ModalScreen):
            return
        acts = self.state.get("actions", [])
        phase = self.state.get("phase")
        wrap_label = {"setup_done": "Finish setup → session 1", "ready": "Start the planned session"
                      }.get(phase, "Wrap session")
        items = [
            ("status", "Campaign status", "status" not in acts),
            ("wrap", f"{wrap_label}  (^w)", "advance" not in acts),
            ("cancel", "Cancel turn  (^x)", "cancel" not in acts),
            ("screen", "Toggle behind-screen  (^g)", False),
            ("mode", f"Switch to {'META' if self.mode == 'action' else 'ACTION'} mode  (^t)",
             "meta" not in acts),
            ("roll", "Roll dice…", False),
            ("quit", "Quit  (^q)", False),
        ]
        self.push_screen(MenuScreen(items), self._menu_selected)

    def _menu_selected(self, choice: str | None) -> None:
        if choice == "status":
            self._send("status")
        elif choice == "wrap":
            self.action_wrap()
        elif choice == "cancel":
            self.action_cancel()
        elif choice == "screen":
            self.action_toggle_screen()
        elif choice == "mode":
            self.action_toggle_mode()
        elif choice == "roll":
            self.push_screen(RollScreen(), self._roll_submitted)
        elif choice == "quit":
            self.exit()

    def _roll_submitted(self, expr: str | None) -> None:
        if expr:
            self._scene_status(roll_expr(expr) or f"could not parse “{escape(expr)}” — try 2d6+3",
                               kind="rule")

    def action_toggle_screen(self) -> None:
        log = self.query_one("#screen", RichLog)
        log.toggle_class("hidden")
        if not log.has_class("hidden"):
            log.scroll_end(animate=False)

    def action_toggle_mode(self) -> None:
        if self.batch or self.state.get("phase") != "play":
            return
        self.mode = "meta" if self.mode == "action" else "action"
        self._sync_input()
        self._refresh_subtitle()
