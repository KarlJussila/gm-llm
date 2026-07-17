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

import json
import re
import secrets
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..orchestrator import (
    Backend, BackendError, CanonPreloader, Gate, Game, Logs, Reconciler,
)
from ..orchestrator.logs import debug_enabled
from ..orchestrator.prompts import player_turn
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


def run_once(run_dir, fixture: dict, *, turn_cap: int = 30, play_only: bool = False,
             kickoff: str = "Let's begin the session.", port: int = 4181,
             min_gap: float = 1.0, turn_timeout: int = 360, stream: bool = False,
             backend_factory=_default_backend, gate_factory=_default_gate,
             reconcile_fn=_default_reconcile, note=_quiet) -> dict:
    """Play one already-assembled run dir through the gated loop and return its record
    (`outcome`, `turns`, `archive`). Boots a backend on the run dir (its own log bundle,
    its own archive), emits the `conditions` event, plays to `task_complete` or the hard
    `turn_cap`, then — on a natural close and unless `play_only` — writes handoff notes
    and reconciles. The backend is always stopped on the way out (sequential runs share a
    port). `BackendError` propagates to the batch loop (recorded as a failed run);
    `KeyboardInterrupt` propagates to abort the whole batch."""
    run_dir = Path(run_dir)
    logs = Logs.under(project=run_dir, debug=debug_enabled())
    backend = backend_factory(run_dir, port=port, min_gap=min_gap,
                              turn_timeout=turn_timeout, logs=logs, note=note)
    record = {"outcome": "failed: no play", "turns": 0}
    tap = None
    try:
        backend.start()
        if stream:
            from ..orchestrator.stream import EventTap
            tap = EventTap(backend.base, backend.directory).start()
        reconcile = not play_only
        _emit_conditions(logs, fixture, turn_cap=turn_cap, reconcile=reconcile, run_dir=run_dir)

        character = _character(run_dir, fixture, note)
        game = Game(backend, gate_factory(backend, run_dir, logs), logs=logs)
        player_sid = backend.create_session("bench-player")
        note(f"runner={game.runner_sid} player={player_sid} session={game.session}")

        tr = game.start(kickoff)
        scene = tr.final

        turns, outcome = 0, "cap"
        while turns < turn_cap:
            turns += 1
            if turns == 1 and character:
                msg = ("[YOUR CHARACTER — read this, then stay in character for the rest "
                       f"of the session]\n\n{character}\n\n" + player_turn(scene))
            else:
                msg = player_turn(scene)
            note(f"turn {turns}/{turn_cap}: player…")
            player = backend.prompt(player_sid, "player", msg)
            note(f"turn {turns}/{turn_cap}: dm (draft + gate)…")
            tr = game.turn(player)
            scene = tr.final
            if tr.session_complete:
                outcome = "complete"
                break

        record["turns"] = turns
        if outcome == "complete":
            note(f"session wrapped naturally after {turns} turn(s).")
            game.handoff()
            if reconcile:
                note(f"reconciling session {game.session}…")
                reconcile_fn(backend, gate_factory(backend, run_dir, logs), logs, game.session)
            record["outcome"] = "complete"
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

def _find_archive(run_dir: Path):
    """The archive a run left behind (glob — its name carries a random suffix), or None
    if the run died before its first emit."""
    hits = sorted((Path(run_dir) / ".opencode" / "logs").glob("archive-*.jsonl"))
    return hits[-1] if hits else None


def _rel(path, base) -> str:
    try:
        return str(Path(path).relative_to(base))
    except ValueError:
        return str(path)


def run_batch(fixture_path, out_dir, *, runs: int = 1, turn_cap: int = 30,
              play_only: bool = False, kickoff: str = "Let's begin the session.",
              port: int = 4181, min_gap: float = 1.0, turn_timeout: int = 360,
              stream: bool = False, init=init_project, install=install_plugin_deps,
              backend_factory=_default_backend, gate_factory=_default_gate,
              reconcile_fn=_default_reconcile, note=_quiet) -> list[dict]:
    """Run a batch of `runs` plays of `fixture_path` under `out_dir`, appending one JSONL
    line per run to `out_dir/batch.jsonl`. Prepares the template once, then per run:
    assemble → play → record. A run that raises `BackendError` (a rate-limit give-up) is
    recorded as failed and the batch continues — batches run overnight on the free tier,
    so one flaky run must not sink the rest. `KeyboardInterrupt` aborts the whole batch
    cleanly. Re-invoking with the same `--out` appends new runs to the same manifest:
    partial batches stay usable, and that is the whole resumability story."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture = load_fixture(fixture_path)
    fixture_campaign = Path(fixture_path) / "campaign"
    manifest = out_dir / "batch.jsonl"

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
        except BackendError as e:
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
