# Frontend / mode modularity — plan of record

**Goal:** any play mode pairs with any frontend. Concretely: watch a `bench` run's play
and reconcile in the TUI, the same way a live campaign is watched today.

`6b4246f` made `play`'s axes expressible — `--player {human,auto}`, `--ui {tui,console}`,
and the backend — but deliberately did not fill the grid, and it scoped the axes to `play`
alone. Two cells exit naming themselves (`gm_llm/cli.py:146`), and `bench` was never on the
axes at all. This doc is the expansion.

## What is already in place

Two of the three seams exist and only need routing.

**Output.** `EventTap(base, directory, write=…, markup=…)` is one implementation with two
dialects: `bench run --stream` passes nothing and gets `_stdout_write` (`stream.py:41`); the
TUI passes `write=stream_write, markup=True` and gets the behind-the-screen pane
(`lifecycle.py:55`). Routing a bench run's stream into a Textual pane is a constructor
argument, not a redesign.

**Combat driving.** One loop, `orchestrator.play_combat` — the agent-player wrapper over
`CombatDriver`: prompt the `player` agent on each PC slot, count each slot against `turn_cap`
(`None` disables), render through three optional hooks. autoplay and `bench run` are dialects
of it (findings Part 3). The `backend.prompt` inside it is where a `PlayerSource` attaches.

**Progress.** Already callback-shaped: `on_stage(key)` for reconcile stages, `Game.on_step`
for per-turn steps (`tui/app.py:91`), `on_tool` for setup. The TUI renders all three today
via `Lifecycle.wrap(on_stage=…)`.

## What is actually in the way

**Drive direction.** The TUI is pull-driven — it idles in `on_input_submitted`, then
`run_worker(self._do_turn(text))`. autoplay and bench are push-driven — a blocking
`for i in range(1, turn_cap + 1)` that calls `backend.prompt(player_sid, …)` and prints.
The `--player auto --ui tui` stub is not a missing flag; it is two independent loops.

**The auto modes bypass `Lifecycle`.** `Lifecycle` is the interface the TUI is written
against (`tui/app.py:36`), but `autoplay.run()` and `bench.runner.run_once()` both construct
`Game` directly (`autoplay.py` `body()`, `runner.py:343`) and reach the reconciler their own
way (`reconcile_fn`). The abstraction that would make them renderable is the one they skip.

## Sequence

Contracts before consumers — the driver unification lands before anything renders it. Step 1
landed (§ What is already in place, "Combat driving"); the numbering is stable, so ROADMAP's
rows keep pointing at the same steps.

2. **`PlayerSource`** — one turn loop, two implementations of "where does the next player
   message come from": keyboard (awaits the frontend) and agent (`backend.prompt` with the
   packet/story intro). `--player` selects. This is what collapses the fork.
3. **Route bench through `Lifecycle`** instead of `reconcile_fn`. Once it does, watching
   reconcile in the TUI is nearly free — the TUI already renders `wrap(on_stage=…)`.
4. **Batch chrome.** `run_batch` stays above the frontend: N runs, per-run backend on a
   shared port, conditions stamping, manifest rewrite, resume classification. None of it is
   per-session. The TUI needs a batch header it has never had (run *k* of *N*, outcome so
   far) because `PlayApp` assumes one campaign directory for the app's whole life.

## Constraints

- **Textual is async; the driver loop blocks.** The TUI already runs blocking calls off the
  UI thread in workers, so this is tractable — but the agent player must not be able to wedge
  the event loop, and `ctrl+x` cancel needs a defined meaning for an unattended run.
- **Comparability is the invariant.** Bench's value is condition-stamped runs that pool.
  Attaching a frontend must be provably inert with respect to what is measured: the frontend
  never touches the archive path. Prefer asserting that to stamping `ui` into `conditions`,
  which would fragment the baseline B3 is meant to bank.
- **Don't widen to a console human frontend.** The other unbuilt cell (`--ui console` with a
  human player) is not on this track. The TUI is the human frontend; the stub is correct.
