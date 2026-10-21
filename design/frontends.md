# Frontends — an engine behind a protocol

**Goal:** a frontend is a client. Everything that decides what happens — phases, input
routing, interrupt policy, combat's confirm gate, what is safe to show — lives in an engine
that speaks a JSON protocol. A frontend renders events and sends commands, and can be
written in any language without importing `gm_llm`. The Textual TUI becomes one client
among several: a plain console client, a script that plays setup, a future web page.

Sequencing lives in `ROADMAP.md` track **frontends**.

## Today

The *loops* are shared: `play_session` is the one turn loop, a `PlayerSource` says who
plays, `PlayHooks` say what renders, and `Lifecycle` ties setup → play → wrap together. A
bench run is a `Lifecycle` too, and `bench run --ui tui` watches it through `BatchHooks`.

The *workflow* is not shared. `tui/app.py` (≈1,300 lines) is in-process and drives the
lifecycle directly, and it owns product decisions no other frontend can reuse:

| Decision | Where it lives today |
|---|---|
| The phase machine — setup done → plan S1 → open S*n* → play → complete → wrap → open S*n*+1, each gated on a yes/no | `_pending`, `action_wrap`, `_session_done`, `_setup_done`, `_do_wrap` |
| What a line of input *is* — a setup answer, a turn, a PC combat action, a confirm (empty) or a reaction, a meta question — and what is refused (a turn after the session ended, a wrap mid-fight) | `on_input_submitted` |
| Threading — the loop's worker, releasing parked threads on quit, hopping back to the UI | `_session_worker`, `_stop_session`, `_ui` |
| Interrupt policy — revert the runner on a cancel, hand the message back, end the loop on a hard failure in a fight | `_on_interrupt`, `_interrupt_ui` |
| The combat confirm gate | `_on_combat_beat`, `_combat_gate` |
| Spoiler-free progress — stage labels, setup activity from the paths the DM writes | `PHASE_LABELS`, `_SETUP_STAGES` |
| Read-only watching of a bench batch | `on_input_submitted`, `action_wrap` |

`autoplay.py` and `bench/runner.py` drive the same objects with their own copies of the
opening and the tail. A frontend that isn't Python, or isn't in this process, has nothing to
talk to.

## The split

### The engine — `gm_llm/engine/`

`Engine` owns one campaign directory for its life (or one bench batch, below). It builds the
backend and the `Lifecycle`, runs every model call on its own worker thread, and holds the
phase machine. Its whole surface:

```python
engine = Engine(directory, player="human", model=None, variant=None, mock=False, port=4181)
engine.subscribe(on_event)   # called with each event dict, on the engine's thread
engine.start()               # emits `hello`, then opens setup or the session
engine.send(command)         # a command dict; never blocks on a model call
engine.close()               # stops the loop, releases parked threads, stops the backend
```

Everything in the table above moves here, unchanged in behaviour. Commands and events are
plain JSON-serializable dicts — no `TurnResult`, no exceptions, no Rich markup cross the
line.

### The protocol

One version number, sent in `hello`. Every message is one JSON object with a `type`.

**State.** The engine emits `state` on every change, and a frontend renders only from it:

```json
{"type": "state", "phase": "play", "session": 3, "awaiting": "turn",
 "busy": null, "player": "human", "in_combat": false,
 "actions": ["input", "meta", "wrap", "status"]}
```

- `phase` — `setup`, `setup_done`, `planning`, `ready` (S*n* planned, not opened), `play`,
  `combat`, `complete` (the runner ended the session), `wrapping`, `closed`.
- `awaiting` — what an `input` will be taken as: `answer` (setup), `turn`, `pc_action`,
  `confirm` (empty confirms, text reacts), or `null` (nothing — the table is working, or the
  next step is an `advance`).
- `busy` — a spoiler-free label while a call is in flight, else `null`.
- `actions` — the commands the engine will accept right now. A frontend greys out what isn't
  listed instead of re-deriving the rules; a command not listed gets an `error` back.

**Commands** (frontend → engine):

| Command | Meaning |
|---|---|
| `input {text}` | The player's line, taken as `awaiting` says. |
| `meta {text}` | An out-of-game question, between turns. |
| `advance` | The pending phase step: plan session 1, open the planned session, or wrap. |
| `cancel` | Abort the call in flight. A cancelled turn leaves no trace and its text comes back in `handback`. |
| `status` | Ask for the disk-only campaign status. |
| `shutdown` | Close the engine. |

**Events** (engine → frontend):

| Event | Carries |
|---|---|
| `hello` | protocol version, gm-llm version, directory, whether it is a batch |
| `state` | as above |
| `say {speaker, text, meta}` | narration: `speaker` is `dm`, `player` (human or agent), or a combatant's name for a combat beat; `text` is markdown |
| `notice {kind, text}` | a scene line: `rule`, `status`, `success`, `error` |
| `stage {phase, key, label}` | a pipeline stage started (setup, wrap, prep), with its spoiler-free label |
| `progress {label}` | setup's spoiler-free activity ("building your character") |
| `stream {source, kind, text}` | behind the screen: model text or a tool call, labelled by agent and session |
| `turn {n, tools}` | a turn's tool summary, behind the screen |
| `context {used, limit}` | the runner's context use after a turn |
| `retry {agent, attempt, wait, reason}` | a backend retry in progress |
| `handback {text}` | a cancelled message, returned to its author |
| `status {...}` | the answer to `status` |
| `error {what, message}` | a refused command or a failed call; the engine stays up |
| `batch {index, total, run, outcome?}` | a bench batch's run starting or closing |

Local conveniences that touch nothing — the dice roller, toggling panes, drafting while the
table works — stay in the frontend. The dice roller moves to a shared module so every client
can import or reimplement it.

### Transports

- **In-process** — `subscribe` and `send`. Tests and Python callers use it directly.
- **stdio** — `gm-llm serve [dir] [--player …] [--mock] [--model …]` speaks the protocol as
  JSON lines: commands on stdin, events on stdout, logs on stderr. Any language can spawn it.
- **A socket or WebSocket** comes with the first frontend that needs one (a browser, or
  reattaching to an engine that outlives its window). Nothing above changes for it.

### Frontends

- **TUI** — spawns `gm-llm serve` and talks stdio, so the boundary is a process boundary
  and the TUI imports nothing from `orchestrator` or `bench`. What remains in `tui/` is
  widgets, keybindings, input drafting, the panes and the markdown renderer. `--mock` passes
  through to the engine, which runs over `MockLifecycle`.
- **Console** — `--ui console` with a human player: a plain prompt over the same protocol,
  about a hundred lines. It is the proof that the split holds, and the way to drive setup
  from a script. Console autoplay becomes the same client with nothing to type.
- **Bench** — `bench run` builds a batch engine: the same events per run, plus `batch`
  events, and `actions` limited to `cancel` and `shutdown`. Read-only watching is enforced by
  the engine, not by each frontend's manners.

## Constraints

- **Comparability is the invariant.** A watched bench run must make the same calls in the
  same order as a headless one. `dev/test_bench_tui.py` keeps asserting it: the same batch,
  headless and watched, yields identical archive event streams. `ui` stays out of the
  recorded conditions.
- **The engine never parks a frontend.** `send` returns at once; every wait (the player's
  next line, the confirm gate) is the engine's own thread, released by `close`.
- **The boundary is tested.** A test fails if `gm_llm/tui` or the console client imports
  from `gm_llm.orchestrator` or `gm_llm.bench`, and the TUI's tests run against a scripted
  event stream with no lifecycle at all.
- **One engine per campaign directory at a time**, as today. The engine dies with the process
  that hosts it; reattaching is the socket transport's job, later.

## Steps

Each step lands with the suite green and the product working.

1. **Engine and protocol, headless.** `gm_llm/engine/` over `Lifecycle`: the phase machine,
   input routing, interrupts, the confirm gate, the labels. Tests drive it over
   `MockLifecycle` command by command and assert the event sequence. The console client on
   top (`--ui console`), replacing the "not implemented" stub.
2. **stdio.** `gm-llm serve`, and a small client class that spawns it. A round-trip test runs
   step 1's script over the pipe.
3. **The TUI as a client.** Port `tui/app.py` onto the client; delete its copies of the
   workflow; the import-boundary test.
4. **Bench through the engine.** The batch engine, `bench run --ui tui` as a client, console
   autoplay as a client; `test_bench_tui` still proves the archives identical.
5. **Docs.** `README.md`'s frontend sections, `design/README.md`'s seams, the protocol table
   above checked against the code.
