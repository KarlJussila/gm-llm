"""
The `bench run` engine — promote the `dev/cli.py play` harness to benchmark grade.

A batch prepares one **template** project once (`gm-llm init` + plugin deps), then for
each run stamps out a fresh project dir from that template plus the fixture's frozen
`campaign/`, plays it through the same gated loop the product uses, and leaves a
condition-stamped score archive behind. The measurement contract (BENCHMARK.md) lives
in the shape of what this writes, not in any judgement it makes: play CAPTURES, the
post-hoc grader (B2) judges.

Two invariants this module owns:

  * **Conditions before play.** Each run emits a `conditions` archive event — fixture
    id/frozen/provisional, tier, turn cap, whether reconcile runs, and the per-agent
    model+temperature parsed from the run dir's own `.opencode/agent/*.md` — *before*
    the first turn. Emitting it first also writes the lazy `run` header, so every
    archive opens `run, conditions, turn, …`: a comparison across mismatched conditions
    is impossible to make by accident.

  * **Turns-to-wrap stays meaningful.** Play runs to the runner's own `task_complete`
    close (decision 3 in BENCHMARK.md), with a hard turn cap as the only safety net. A
    cap breach is stamped into the archive (a `cap` event) and skips reconcile — an
    unwrapped session has no clean transcript end — so a run that never learned to wrap
    can't masquerade as one that did.

Everything expensive is injected (`backend_factory`, `gate_factory`, `reconcile_fn`,
and the `init`/`install` callables on `prepare_template`) so `dev/test_bench.py` can
exercise the assembly, conditions, loop, cap, and batch-resilience logic with no
network, no npm, and no opencode. The defaults wire up the real orchestrator.
"""

from __future__ import annotations

import dataclasses
import json
import re
import secrets
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..orchestrator import (
    Archive, Backend, BackendError, CanonPreloader, CombatDriver, Gate, Game, Logs,
    Reconciler,
)
from ..orchestrator.logs import debug_enabled
from ..orchestrator.prompts import player_combat_turn, player_turn
from ..project import init_project, install_plugin_deps

# Which agents' model/temperature get stamped into the conditions event. dm-runner and
# narrative-checker are the live subject+instrument; player is the autoplayer; dm is the
# between-session author the reconcile pass drives. Enough to reconstruct the condition.
_CONDITION_AGENTS = ("dm-runner", "player", "narrative-checker", "dm")

TIER = "low"  # the product IS the low tier (BENCHMARK.md); bench run only plays it today.


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_id() -> str:
    """A sortable run id: start-time + a short random suffix (two runs in the same
    second must land in distinct dirs). Mirrors `Archive.under`'s scheme."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)


def _quiet(msg: str) -> None:  # default `note` — the CLI passes its own coloured one
    print(f"[bench] {msg}", flush=True)


# ── fixture + conditions ─────────────────────────────────────────────────────

def load_fixture(fixture_path) -> dict:
    """Read a fixture's `fixture.json`. `fixture_path` is the fixture dir (which holds
    `campaign/` and `fixture.json`); the returned dict carries at least `id`, `frozen`,
    `provisional`, and `character_packet` (a path relative to the run dir)."""
    fixture_path = Path(fixture_path)
    data = json.loads((fixture_path / "fixture.json").read_text(encoding="utf-8"))
    data.setdefault("id", fixture_path.name)
    return data


def agent_conditions(run_dir, agents=_CONDITION_AGENTS) -> dict:
    """Parse `{model, temperature}` from each agent's YAML frontmatter in the run dir's
    `.opencode/agent/*.md`. A tiny manual parser — the repo carries no yaml dep, and
    `completeness._frontmatter_type` reads frontmatter the same hand-rolled way. A
    missing file or field yields `None` rather than raising: the archive records what it
    could read, and a gap is itself a signal worth seeing."""
    agent_dir = Path(run_dir) / ".opencode" / "agent"
    out: dict[str, dict] = {}
    for name in agents:
        model, temp = None, None
        try:
            text = (agent_dir / f"{name}.md").read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text.startswith("---"):
            end = text.find("\n---", 3)
            block = text[3:end] if end != -1 else ""
            for line in block.splitlines():
                if (m := re.match(r"\s*model:\s*(\S+)", line)):
                    model = m.group(1).strip()
                elif (m := re.match(r"\s*temperature:\s*([0-9.]+)", line)):
                    temp = float(m.group(1))
        out[name] = {"model": model, "temperature": temp}
    return out


def _emit_conditions(logs, fixture: dict, *, turn_cap: int, reconcile: bool,
                     run_dir: Path) -> None:
    """The `conditions` event — the first emit on the archive, so it rides right behind
    the lazy `run` header (which already carries the gm-llm version)."""
    if not (logs and logs.archive):
        return
    logs.archive.emit(
        "conditions",
        fixture={"id": fixture.get("id"), "frozen": fixture.get("frozen"),
                 "provisional": fixture.get("provisional")},
        tier=TIER, turn_cap=turn_cap, reconcile=reconcile,
        agents=agent_conditions(run_dir),
    )


# ── run-dir assembly ─────────────────────────────────────────────────────────

def prepare_template(out_dir, *, init=init_project, install=install_plugin_deps,
                     note=_quiet) -> Path:
    """Prepare (once) the batch's template project under `out_dir/template`: lay in the
    opencode assets and install the plugin deps. Idempotent — a re-invoked batch with an
    existing template reuses it, so runs never re-pay the npm install. Runs copytree this
    into place; the fixture's `campaign/` is layered on top per run."""
    template = Path(out_dir) / "template"
    if (template / ".opencode").is_dir():
        note(f"reusing template at {template}")
        return template
    note(f"preparing template at {template} (init + plugin deps)…")
    template.mkdir(parents=True, exist_ok=True)
    init(template)
    ok, msg = install(template / ".opencode")
    note(msg if ok else f"WARNING: {msg}")
    return template


def assemble_run(template_dir, fixture_campaign, run_dir, fixture_id: str) -> None:
    """Stamp out one run project: copytree the template (the `.opencode/` scaffold), lay
    the fixture's frozen `campaign/` over it, gitignore `.opencode/` (as the scaffolder
    does), then `git init` + commit the initial state. The reconcile pipeline commits
    into this repo, so the run needs a real one with the fixture as its first commit —
    the fixture dir itself is never played in place.

    `scaffold_campaign` would return early here (campaign/ is already populated), so this
    owns the git init + initial commit that a normal `gm-llm init` gets from the
    scaffolder."""
    run_dir = Path(run_dir)
    shutil.copytree(template_dir, run_dir)
    shutil.copytree(fixture_campaign, run_dir / "campaign", dirs_exist_ok=True)

    gitignore = run_dir / ".gitignore"
    if ".opencode/" not in (gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""):
        with gitignore.open("a", encoding="utf-8") as f:
            f.write(".opencode/\n")

    subprocess.run(["git", "init"], cwd=run_dir, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=run_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"bench: fixture {fixture_id} initial state"],
                   cwd=run_dir, capture_output=True)


# ── backend / gate / reconcile — injectable seams ────────────────────────────

def _default_backend(directory, *, port, min_gap, turn_timeout, logs, note=_quiet):
    b = Backend(directory, port=port, min_call_gap=min_gap, turn_timeout=turn_timeout,
                logs=logs)
    b.on_retry = lambda agent, attempt, wait, reason: note(
        f"{agent} call failed: {reason} — retry {attempt} in {wait}s")
    return b


def _default_gate(backend, directory, logs):
    return Gate(backend, CanonPreloader(directory), logs=logs)


def _default_reconcile(backend, gate, logs, n: int) -> None:
    Reconciler(backend, gate, logs=logs).reconcile_session(n, commit=True, prep=True)


# ── one run ──────────────────────────────────────────────────────────────────

def _character(run_dir: Path, fixture: dict, note) -> str:
    """The player's character packet, read from the fixture path inside the run dir with
    HTML comments stripped — same handling as `cmd_play`."""
    rel = fixture.get("character_packet")
    if not rel:
        return ""
    path = run_dir / rel
    if not path.is_file():
        note(f"WARNING: no character packet at {rel} — player runs blind")
        return ""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL).strip()
    note(f"player packet: {rel} ({len(text)} chars)")
    return text


def _play_combat(game, backend, player_sid, entry_scene, turns: int, turn_cap: int, note):
    """Drive a fight through the library's `CombatDriver`, minimal output. **Each PC slot
    counts as one turn against `turn_cap`** — a fight must not make a run uncappable, and a
    PC slot is the combat analogue of a normal player turn (the beat the autoplayer acts
    on). NPC beats are pumped and confirmed by the driver (no per-beat turn cost). Returns
    `(exit_scene, turns, hit_cap)`: the narration to resume from, the updated turn count,
    and whether the cap was reached mid-fight — a cap breach the caller treats like any
    other (an unfinished fight has no clean wrap, so reconcile is skipped)."""
    driver = CombatDriver(game)
    state = {"scene": entry_scene}

    def on_beat(narration, who):
        state["scene"] = narration
        return None  # autoplay never interjects

    event = driver.advance(on_beat)
    while event.kind == "pc_slot":
        if turns >= turn_cap:
            return state["scene"], turns, True
        turns += 1
        note(f"turn {turns}/{turn_cap}: combat PC slot…")
        player = backend.prompt(player_sid, "player", player_combat_turn(state["scene"]))
        event = driver.pc_action(player, on_beat)
    return event.narration, turns, False


def run_once(run_dir, fixture: dict, *, turn_cap: int = 50, play_only: bool = False,
             kickoff: str = "Let's begin the session.", port: int = 4181,
             min_gap: float = 1.0, turn_timeout: int = 360, stream: bool = False,
             resume: bool = False, backend_factory=_default_backend,
             gate_factory=_default_gate, reconcile_fn=_default_reconcile,
             note=_quiet) -> dict:
    """Play one already-assembled run dir through the gated loop and return its record
    (`outcome`, `turns`, `archive`). Boots a backend on the run dir (its own log bundle,
    its own archive), emits the `conditions` event, plays to `task_complete` or the hard
    `turn_cap`, then — on a natural close and unless `play_only` — writes handoff notes
    and reconciles. The backend is always stopped on the way out (sequential runs share a
    port). `KeyboardInterrupt` propagates to abort the whole batch.

    **Rate limits don't burn progress.** A `BackendError` mid-play (the backend's own
    retry ladder gave up — almost always a sustained rate limit, which minutes of backoff
    won't clear) with real turns behind it is recorded as `"incomplete: …"`, not failed:
    the transcript + archive are on disk, so `bench run --resume` can pick the run back up.
    A give-up before any turn landed is still a genuine `"failed: …"`. A `BackendError`
    before play even starts (server never came up) propagates to the batch loop.

    **`resume=True`** continues an interrupted run in place instead of starting fresh:
    it re-opens the run's own archive (append, no new file — so the grader reads one
    coherent turn stream), re-primes the runner from the transcript via `Game.resume()`,
    continues turn ids and the cap past what's on disk, and skips a second `conditions`
    event. The autoplayer gets a fresh session (its intra-session memory isn't restored),
    so it's re-handed its character packet on the first resumed turn and plays off the
    current scene — fine for the measured subject (runner + checker), which do get full
    context back.

    Combat (a turn that calls `start_encounter`) hands off to `_play_combat`, which drives
    the fight through the `CombatDriver` and counts **each PC slot as one turn** against
    `turn_cap` — so a fight can't make a run uncappable. A fight that runs into the cap is a
    cap breach like any other (reconcile skipped)."""
    run_dir = Path(run_dir)
    logs = Logs.under(project=run_dir, debug=debug_enabled())

    existing = _find_archive(run_dir, note=note) if resume else None
    resuming, turns_done = False, 0
    if existing is not None:
        _, turns_done = classify_archive(existing)
        # Continue the run's own archive so turns 1..k and k+1.. are one stream the grader
        # reads whole (Archive re-heads only a fresh file). Logs is frozen — swap via replace.
        run_id = existing.stem.replace("archive-", "", 1)
        logs = dataclasses.replace(logs, archive=Archive(existing, run_id))
        resuming = True

    backend = backend_factory(run_dir, port=port, min_gap=min_gap,
                              turn_timeout=turn_timeout, logs=logs, note=note)
    record = {"outcome": "failed: no play", "turns": turns_done}
    tap = None
    try:
        backend.start()
        if stream:
            from ..orchestrator.stream import EventTap
            tap = EventTap(backend.base, backend.directory).start()
        reconcile = not play_only

        character = _character(run_dir, fixture, note)
        game = Game(backend, gate_factory(backend, run_dir, logs), logs=logs)
        player_sid = backend.create_session("bench-player")
        note(f"runner={game.runner_sid} player={player_sid} session={game.session}")

        scene = None
        if resuming:
            game._turn_no = turns_done  # continue archive turn ids past what's on disk
            note(f"resuming from {turns_done} turn(s) on disk…")
            scene = game.resume()  # None if the transcript is gone → fall through to a clean open
            if scene is None:
                resuming = False
        if not resuming:
            _emit_conditions(logs, fixture, turn_cap=turn_cap, reconcile=reconcile,
                             run_dir=run_dir)
            scene = game.start(kickoff).final

        turns, outcome, interrupted = turns_done, "cap", None
        primed = False  # the fresh player session gets its packet on the first turn we run
        try:
            while turns < turn_cap:
                turns += 1
                if not primed and character:
                    msg = ("[YOUR CHARACTER — read this, then stay in character for the rest "
                           f"of the session]\n\n{character}\n\n" + player_turn(scene))
                else:
                    msg = player_turn(scene)
                primed = True
                note(f"turn {turns}/{turn_cap}: player…")
                player = backend.prompt(player_sid, "player", msg)
                note(f"turn {turns}/{turn_cap}: dm (draft + gate)…")
                tr = game.turn(player)
                scene = tr.final
                if tr.combat_started:
                    scene, turns, hit_cap = _play_combat(
                        game, backend, player_sid, scene, turns, turn_cap, note)
                    if hit_cap:
                        break  # unfinished fight — a cap breach; outcome stays "cap"
                    continue
                if tr.session_complete:
                    outcome = "complete"
                    break
        except BackendError as e:
            if turns <= 0:
                raise  # gave up before any play landed — a genuine failure, nothing to resume
            interrupted = e

        record["turns"] = turns
        if interrupted is not None:
            note(f"interrupted after {turns} turn(s): {interrupted} — "
                 f"resumable with `bench run --resume`.")
            record["outcome"] = f"incomplete: {interrupted}"
        elif outcome == "complete":
            note(f"session wrapped naturally after {turns} turn(s).")
            # Play wrapped — that's the measured subject and it's settled. Handoff and
            # reconcile are best-effort post-play bookkeeping; a stall there (a rate limit,
            # or a slow large-input call the retries gave up on) must NOT demote a wrapped
            # run to incomplete/failed, or the archive would say "complete" while the
            # manifest says otherwise — and `--resume` (which classifies from the archive)
            # would then skip it forever, stranding the contradiction.
            record["outcome"] = "complete"
            try:
                game.handoff()
                if reconcile:
                    note(f"reconciling session {game.session}…")
                    reconcile_fn(backend, gate_factory(backend, run_dir, logs), logs,
                                 game.session)
            except BackendError as e:
                note(f"post-wrap step gave up ({e}) — session already wrapped; "
                     f"leaving reconcile undone.")
        else:
            note(f"hit the turn cap ({turn_cap}) without a wrap — skipping reconcile.")
            if logs and logs.archive:
                logs.archive.emit("cap", turn=turns)
            record["outcome"] = "cap"
    finally:
        if tap:
            tap.stop()
        note("stopping backend…")
        backend.stop()
    if logs and logs.archive and logs.archive.path.is_file():
        record["archive"] = str(logs.archive.path)
    return record


# ── batch ────────────────────────────────────────────────────────────────────

def _find_archive(run_dir: Path, note=None):
    """The archive a run left behind (glob — its name carries a random suffix), or None
    if the run died before its first emit.

    A run dir should hold exactly one. Two means something wrote a second stream into it
    (historically: reconcile invoked as its own `bench run` instead of `--resume`), and the
    loser is invisible to both the manifest and the grader — its stage findings score as if
    they never happened. Resume takes the newest, which is nearly always the live one, but
    says so loudly: a silent pick is how the split-archive bug went unnoticed for a week."""
    hits = sorted((Path(run_dir) / ".opencode" / "logs").glob("archive-*.jsonl"))
    if len(hits) > 1 and note:
        others = ", ".join(p.name for p in hits[:-1])
        note(f"WARNING: {len(hits)} archives in {Path(run_dir).name} — resuming the newest "
             f"({hits[-1].name}); NOT part of this run: {others}. Fold them in or delete "
             f"them, or their findings never reach the grader.")
    return hits[-1] if hits else None


def classify_archive(archive_path) -> tuple[str, int]:
    """Read a run's archive and say where it stands, using the same signals scoring.py
    derives outcome from: a `cap` event means it ran to the cap, and the *last* turn
    event's `session_complete` means it wrapped. Returns `(state, turns)` where `turns`
    is the count of `turn` events and `state` is one of:

      * ``"complete"`` — the session wrapped; nothing to resume.
      * ``"capped"``   — it hit the turn cap; a terminal outcome, nothing to resume.
      * ``"resumable"``— turns landed but it neither wrapped nor capped (a rate-limit
                         give-up, a crash, a Ctrl-C): the transcript is on disk and
                         `bench run --resume` can continue it.
      * ``"empty"``    — no turns (or no archive): nothing to resume.

    Pure archive read, no backend — so a resume sweep can classify a whole batch cheaply."""
    path = Path(archive_path) if archive_path else None
    if not path or not path.is_file():
        return ("empty", 0)
    turns, capped, last_complete = 0, False, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "turn":
            turns += 1
            last_complete = bool(e.get("session_complete"))
        elif e.get("event") == "cap":
            capped = True
    if last_complete:
        return ("complete", turns)
    if capped:
        return ("capped", turns)
    return ("resumable", turns) if turns else ("empty", 0)


def _rewrite_manifest(manifest: Path, record: dict) -> None:
    """Replace the `batch.jsonl` line for `record["run_dir"]` with `record` (append if
    absent), collapsing to one line per run dir. A resumed run continues the same archive,
    so its manifest line is *updated in place* — the aggregators read one line per run and
    must not see a run twice."""
    run_dir = record.get("run_dir")
    kept: list[str] = []
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("run_dir") != run_dir:
                kept.append(line)
    kept.append(json.dumps(record, ensure_ascii=False))
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _rel(path, base) -> str:
    try:
        return str(Path(path).relative_to(base))
    except ValueError:
        return str(path)


def _resume_batch(out_dir: Path, manifest: Path, fixture: dict, *, turn_cap: int,
                  play_only: bool, kickoff: str, port: float, min_gap: float,
                  turn_timeout: int, stream: bool, backend_factory, gate_factory,
                  reconcile_fn, note) -> list[dict]:
    """`--resume`: pick every *incomplete* run in `out_dir` (rate-limited / crashed / Ctrl-C'd
    — an archive with turns but neither a wrap nor a cap) back up and continue it in place,
    updating its manifest line. Complete and capped runs are terminal and skipped; runs with
    no turns have nothing to resume. Does NOT start fresh runs — resume tops up what's there."""
    records: list[dict] = []
    if not manifest.is_file():
        note(f"no batch.jsonl under {out_dir} — nothing to resume.")
        return records
    latest: dict[str, dict] = {}  # last manifest line wins per run dir
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            latest[rec.get("run_dir")] = rec

    pending = []
    for rd, rec in latest.items():
        arc = out_dir / rec["archive"] if rec.get("archive") else None
        state, done = classify_archive(arc)
        if state == "resumable":
            pending.append((rd, rec, done))
    if not pending:
        note("no resumable (incomplete) runs found — nothing to resume.")
        return records

    note(f"resuming {len(pending)} incomplete run(s)…")
    for rd, rec, done in pending:
        run_dir = out_dir / rd
        note(f"── resume {rd} (from {done} turn(s)) ──")
        try:
            result = run_once(
                run_dir, fixture, turn_cap=turn_cap, play_only=play_only, kickoff=kickoff,
                port=port, min_gap=min_gap, turn_timeout=turn_timeout, stream=stream,
                resume=True, backend_factory=backend_factory, gate_factory=gate_factory,
                reconcile_fn=reconcile_fn, note=note)
        except KeyboardInterrupt:
            note("batch aborted (Ctrl-C).")
            raise
        except BackendError as e:  # backend never came up — leave the run resumable
            note(f"resume failed: {e}")
            result = {"outcome": f"incomplete: {e}", "turns": done}

        record = {**rec, "finished": _now(), "outcome": result["outcome"],
                  "turns": result.get("turns", done)}
        if result.get("archive"):
            record["archive"] = _rel(result["archive"], out_dir)
        _rewrite_manifest(manifest, record)
        records.append(record)
        note(f"resume {rd}: {record['outcome']} ({record['turns']} turn(s))")
    return records


def run_batch(fixture_path, out_dir, *, runs: int = 1, turn_cap: int = 50,
              play_only: bool = False, kickoff: str = "Let's begin the session.",
              port: int = 4181, min_gap: float = 1.0, turn_timeout: int = 360,
              stream: bool = False, resume: bool = False, init=init_project,
              install=install_plugin_deps, backend_factory=_default_backend,
              gate_factory=_default_gate, reconcile_fn=_default_reconcile,
              note=_quiet) -> list[dict]:
    """Run a batch of `runs` plays of `fixture_path` under `out_dir`, appending one JSONL
    line per run to `out_dir/batch.jsonl`. Prepares the template once, then per run:
    assemble → play → record. `KeyboardInterrupt` aborts the whole batch cleanly.

    Two kinds of resilience, both so an overnight free-tier batch survives rate limits:

      * A run whose backend gives up mid-play (a sustained rate limit) is recorded
        `"incomplete: …"` with its turns intact — the run dir holds the transcript, so it
        can be continued later. Only a give-up *before play starts* is `"failed: …"`. Either
        way the batch continues — one flaky run must not sink the rest.
      * **`resume=True`** ignores `runs` and instead continues every incomplete run already
        under `out_dir` in place (see `_resume_batch`), updating its manifest line. Run a
        fresh batch, then `--resume` after the caps clear to top up the incompletes.

    Re-invoking without `--resume` and the same `--out` still just appends new fresh runs."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture = load_fixture(fixture_path)
    fixture_campaign = Path(fixture_path) / "campaign"
    manifest = out_dir / "batch.jsonl"

    if resume:
        return _resume_batch(
            out_dir, manifest, fixture, turn_cap=turn_cap, play_only=play_only,
            kickoff=kickoff, port=port, min_gap=min_gap, turn_timeout=turn_timeout,
            stream=stream, backend_factory=backend_factory, gate_factory=gate_factory,
            reconcile_fn=reconcile_fn, note=note)

    template = prepare_template(out_dir, init=init, install=install, note=note)

    records: list[dict] = []
    for i in range(runs):
        runid = _run_id()
        run_dir = out_dir / f"run-{runid}"
        note(f"── run {i + 1}/{runs} · {runid} ──")
        assemble_run(template, fixture_campaign, run_dir, fixture.get("id", "fixture"))
        started = _now()
        try:
            result = run_once(
                run_dir, fixture, turn_cap=turn_cap, play_only=play_only, kickoff=kickoff,
                port=port, min_gap=min_gap, turn_timeout=turn_timeout, stream=stream,
                backend_factory=backend_factory, gate_factory=gate_factory,
                reconcile_fn=reconcile_fn, note=note)
        except KeyboardInterrupt:
            note("batch aborted (Ctrl-C).")
            raise
        except BackendError as e:  # gave up before play started (server never came up)
            note(f"run failed: {e}")
            arc = _find_archive(run_dir)
            result = {"outcome": f"failed: {e}", "turns": 0,
                      "archive": str(arc) if arc else None}

        arc = result.get("archive")
        record = {
            "run": runid,
            "run_dir": _rel(run_dir, out_dir),
            "archive": _rel(arc, out_dir) if arc else None,
            "started": started,
            "finished": _now(),
            "outcome": result["outcome"],
            "turns": result.get("turns", 0),
        }
        with manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        records.append(record)
        note(f"run {runid}: {record['outcome']} ({record['turns']} turn(s))")
    return records
