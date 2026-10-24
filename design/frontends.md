# Frontends — an engine behind a protocol

A frontend is a client. Everything that decides what happens — phases, what a line of input
is taken as, the interrupt policy, combat's confirm gate, the spoiler-free labels — lives in
the engine, which speaks a JSON protocol. A frontend renders events and sends commands, so it
can be written in any language without importing `gm_llm`.

## The pieces

- **The engine** — `gm_llm/engine/core.py`. `Engine` owns one campaign's `Lifecycle` for its
  life: it opens setup or the session, runs every model call on its own threads, and holds
  the phase machine. `send` never blocks on a model call. `open_engine` builds one over the
  real backend or over `MockLifecycle`.
- **The batch engine** — `gm_llm/bench/watch.py`. `BatchEngine` puts a bench batch behind the
  same protocol. The batch drives itself; each run's lifecycle is attached as it opens, and
  its turns render through the engine's hooks composed under bench's own (`BatchHooks`).
- **stdio** — `gm-llm serve [dir]` (and `bench run --ui serve`) speak the protocol as JSON
  lines: commands on stdin, events on stdout, everything else on stderr. The engine closes
  when stdin does.
- **The client** — `gm_llm/engine/client.py`, the only engine module a frontend imports.
  `ProcessClient` spawns the child in its own process group, so the terminal's Ctrl+C
  reaches only the frontend; `LocalClient` wraps an engine in-process for tests.
- **Frontends** — the Textual TUI (`gm_llm/tui/`), which spawns `gm-llm serve`; the console
  (`gm_llm/consoleui.py`, `play --ui console`, human or agent player); and the TUI watching
  a batch (`bench run --ui tui` spawns `bench run --ui serve`). The dice roller
  (`gm_llm/dice.py`) touches nothing, so it stays in the frontend.

## The protocol

Version 1, sent in `hello`. Every message is one JSON object with a `type`.

**State.** The engine emits `state` on every change, and a frontend renders from it:

```json
{"type": "state", "phase": "play", "session": 3, "awaiting": "turn",
 "busy": null, "player": "human", "in_combat": false,
 "actions": ["status", "shutdown", "input", "meta", "advance"]}
```

- `phase` — `starting`, `setup`, `setup_done` (setup committed, but planning session 1
  failed), `planning`, `ready` (session *n* planned, not opened), `play`, `complete` (the runner
  ended the session), `wrapping`, `closed`. Setup rolls straight into planning session 1.
- `awaiting` — what an `input` will be taken as: `answer` (setup), `turn`, `pc_action`,
  `confirm` (empty confirms, text reacts), or `null`.
- `busy` — a spoiler-free label while a call is in flight, else `null`.
- `actions` — the commands the engine accepts right now. Anything else gets an `error` and
  changes nothing.

**Commands** (frontend → engine):

| Command | Meaning |
|---|---|
| `input {text}` | The player's line, taken as `awaiting` says. |
| `meta {text}` | An out-of-game question, between turns. |
| `advance` | The next phase step: retry planning session 1, open the planned session, or wrap (mid-play too). |
| `cancel` | Abort the call in flight. A cancelled turn leaves no trace and comes back in `handback`. |
| `status` | Ask for the disk-only campaign status. |
| `shutdown` | Close the engine. |

**Events** (engine → frontend):

| Event | Carries |
|---|---|
| `hello` | `protocol`, `version`, `directory`, `batch` |
| `state` | as above |
| `say {speaker, text, meta, combatant}` | `speaker` is `dm` or `player`; `combatant` names whose combat beat it is (`pc` for the player's); `text` is markdown |
| `notice {kind, text}` | a scene line: `status`, `rule`, `success` or `error` |
| `stage {phase, key, label}` | a setup or wrap stage started, with its spoiler-free label |
| `progress {label}` | setup's spoiler-free activity, each label once |
| `stream {kind, text}` | behind the screen: `heading`, `text`, `reasoning`, `tool`, or a bench `note` |
| `turn {n, tools}` | a turn's tool summary |
| `context {tokens, limit, pct}` | the runner's context use after a turn |
| `retry {agent, attempt, of, wait, reason}` | a backend retry in progress |
| `handback {text}` | a cancelled message, returned to its author |
| `status {...}` | the answer to `status` (`CampaignStatus`'s fields) |
| `error {what, message}` | a refused command or a failed call; the engine stays up |
| `batch {event, …}` | `run` (`index`, `total`, `run`), `close` (`record`), or `done` |

## Constraints

- **Comparability is the invariant.** A watched bench run makes the same calls in the same
  order as a headless one: `BatchEngine` offers only `cancel` and `shutdown`, and skips the
  context readout. `dev/test_bench_tui.py` plays the same batch headless and watched (typing
  into the watching app on the way past) and requires identical archive event streams. `ui`
  stays out of the recorded conditions.
- **The engine never parks a frontend.** Every wait — the player's next line, the confirm
  gate — is on the engine's own threads, released by `close`. Subscribers are called under
  the engine's lock, so they must not block.
- **The boundary is tested.** `dev/test_tui_loop.py` fails if the TUI or the console imports
  the orchestrator, the bench or the engine core.
- **One engine per campaign directory**, dying with the process that hosts it. Reattaching
  to an engine that outlives its window would come with a socket transport.
