# Frontend / mode modularity — plan of record

**Goal:** any play mode pairs with any frontend. Concretely: watch a `bench` run's play
and reconcile in the TUI, the same way a live campaign is watched today.

`6b4246f` made `play`'s axes expressible — `--player {human,auto}`, `--ui {tui,console}`,
and the backend — but deliberately did not fill the grid, and it scoped the axes to `play`
alone. Two cells exited naming themselves, and `bench` was never on the axes at all. This
doc is the expansion.

## What is already in place

**Output.** `EventTap(base, directory, write=…, markup=…)` is one implementation with two
dialects: `bench run --stream` passes nothing and gets `_stdout_write` (`stream.py:41`); the
TUI passes `write=stream_write, markup=True` and gets the behind-the-screen pane
(`lifecycle.py`). Routing a bench run's stream into a Textual pane is a constructor
argument, not a redesign.

**Combat driving.** One loop, `orchestrator.play_combat` — the wrapper over `CombatDriver`
that adds what the driver leaves out: soliciting the player on each PC slot, and counting
each slot against `turn_cap` (`None` disables). Renders through the play layer's hooks
(findings Part 3, extended in Part 4).

**The turn loop.** `orchestrator.play_session` — one loop for every player and every
frontend (findings Part 4). Where the next message comes from is a `PlayerSource`
(`AgentPlayer` prompts the `player` agent and primes the packet; `KeyboardPlayer` parks the
loop's thread until a frontend hands a line in); what renders is `PlayHooks`. The loop owns
the packet framing, cap accounting, the combat handoff and the wrap signal, and nothing
else: the session opening and the post-session tail stay with the caller, which is where
they actually differ.

**Progress.** Already callback-shaped: `on_stage(key)` for reconcile stages, `Game.on_step`
for per-turn steps, `on_tool` for setup. The TUI renders all three today via
`Lifecycle.wrap(on_stage=…)`.

**A bench run is a `Lifecycle`.** `bench.runner.run_once` no longer wires its own `Game`,
player session and reconciler: it builds the lifecycle (through an injectable
`lifecycle_factory`), plays `lifecycle.player_source()`, and its post-wrap tail is
`lifecycle.wrap(on_stage=…)` — so the run already emits the stage protocol a frontend
renders (findings Part 5). What stays bench's is what is actually bench's: the run dir, the
conditions event, the archive continuation, and how an outcome is recorded.

**A batch is a `Lifecycle` per run.** `PlayApp` no longer assumes one campaign directory for
the app's life: `self.lc` is *attached per run* (None between runs, with `phase` answering
for it) and the batch stays above the frontend, on its own thread, calling back through
`bench.runner.BatchHooks` — `on_run` / `on_open` → `PlayHooks` / `on_stage` / `on_close`.
`bench run --ui tui` is the wiring. `BatchHeader` is the chrome a batch needs and a session
never did: run *k* of *N*, outcome so far (findings Part 6).

**Watching is read-only, and that is enforced.** `BatchHooks` composes the frontend's hooks
*under* bench's own bookkeeping rather than replacing them, so a watched run counts turns and
gives up in the same places an unwatched one does; nothing typed reaches a run; `ctrl+w` is
refused (a run wraps itself); and the per-turn context readout is skipped. `ctrl+x` is the
one affordance that carries over verbatim — abort the call in flight, the loop asks again
from the same scene — because a cancelled turn provably leaves no trace in transcript, canon
or archive. Quitting stops the loop, which ends that run `incomplete`/resumable (never a
`cap`, which would archive a ceiling it never hit) and ends the batch.

## What is actually in the way

**Console autoplay still wires its own `Game`.** `autoplay.run()` is the last direct
constructor. Nothing is blocked by it — the mode×frontend cell it serves works, and the TUI's
auto cell already runs on the real lifecycle — so this is duplication to retire, not a gap to
close. It needs `player_source()` to carry the resume story an `AgentPlayer` primes with,
which is a contract question of its own. Step 5.

## Sequence

Contracts before consumers — the driver unification lands before anything renders it. Steps
1–4 have landed (§ What is already in place); the numbering is stable, so ROADMAP's rows
keep pointing at the same steps.

5. **Route console autoplay through `Lifecycle`** — the last direct `Game` construction.
   Unblocks nothing; retires the duplication.

## Constraints

- **Textual is async; the loop blocks.** Settled in step 2 and binding on what follows: the
  loop runs in one worker thread per session and the frontend feeds it from the UI thread.
  Everything the worker can park on — the player source, combat's confirm gate — must be
  released when the app goes down, or a parked pool thread keeps the interpreter from
  exiting; and a hook that fires after the app has stopped must be a no-op rather than a
  wait on a dead event loop.
- **Comparability is the invariant.** Bench's value is condition-stamped runs that pool.
  Attaching a frontend must be provably inert with respect to what is measured: the frontend
  never touches the archive path. That is now *asserted* rather than argued —
  `dev/test_bench_tui.py` plays the same batch headless and watched (typing into the watching
  app on the way past) and requires the two archives' event streams to be identical. Which is
  why `ui` is not a recorded condition: stamping it would fragment the baseline B3 is meant
  to bank, and there is nothing for it to explain.
- **Don't widen to a console human frontend.** The other unbuilt cell (`--ui console` with a
  human player) is not on this track. The TUI is the human frontend; the stub is correct.
