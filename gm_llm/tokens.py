"""
`gm-llm tokens` — what a campaign or a benchmark batch cost, in tokens.

opencode already records this: every session row in its store carries `directory` plus
pre-aggregated `tokens_input / tokens_output / tokens_reasoning / tokens_cache_read /
tokens_cache_write` and `cost`. A prefix match on `directory` therefore scopes any tree —
one campaign, or one bench run, which plays in its own dir. That makes this **retroactive**:
work already on disk reports without ever having been instrumented. Nothing is emitted
during play.

Two things this module is careful about:

  * **It reads someone else's schema.** The store is opencode's private SQLite, not our
    archive, and it can change shape under a version bump. Every query is read-only
    (`mode=ro`) and every failure — missing file, renamed table, absent column — returns
    an empty reading with a reason rather than raising. A token report is a curiosity; it
    must never break `bench report` or a run.

  * **It does not invent prices.** `cost` is whatever opencode recorded, which on a free
    tier is `0.00`. Dollar figures appear only when the caller passes an explicit rate
    card (`--price-in/--price-out/--price-cache-read`), and they are labelled as the
    hypothetical they are.

The reasoning-token caveat is real and unresolved upstream: opencode stores
`tokens_reasoning` separately, and whether a provider bills it inside `output` or on top
varies. `Usage.priced()` reports the `output`-only figure and hands back the reasoning
surcharge separately so a reader can decide, rather than picking one and hiding it.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

# opencode's store. `OPENCODE_DATA` overrides, matching opencode's own env handling; the
# `-local` variant is the fallback some installs write instead.
_DEFAULT_DATA = Path(os.environ.get("OPENCODE_DATA")
                     or (Path.home() / ".local" / "share" / "opencode"))
_DB_NAMES = ("opencode.db", "opencode-local.db")

_COLUMNS = ("tokens_input", "tokens_output", "tokens_reasoning",
            "tokens_cache_read", "tokens_cache_write")

# opencode 1.x wrote sessions to `session`; 2.x writes them to `session_v2`, same columns. A
# store upgraded across the two holds both, so a scope's usage is the sum over each.
_SESSION_TABLES = ("session", "session_v2")


@dataclass
class Usage:
    """One scope's token totals. `sessions` is how many opencode sessions rolled up —
    a play run spans dozens (each checker dispatch is its own), not one."""
    sessions: int = 0
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(*(getattr(self, f) + getattr(other, f) for f in
                       ("sessions", "input", "output", "reasoning",
                        "cache_read", "cache_write", "cost")))

    @property
    def uncached(self) -> int:
        """Tokens that were not a cache hit — the number that tracks real work done."""
        return self.input + self.output + self.cache_write

    def priced(self, per_m_in: float, per_m_out: float, per_m_cache_read: float,
               per_m_cache_write: float | None = None) -> dict:
        """Cost at an explicit rate card, in dollars per million tokens. Cache writes bill
        at `per_m_cache_write` when given, else at the input rate (the usual convention).

        `reasoning_surcharge` is what reasoning tokens would add *if* the provider bills
        them on top of `output` rather than inside it — reported separately because which
        one is true depends on the provider, and silently choosing would misstate the
        total by whichever amount is wrong."""
        cw_rate = per_m_in if per_m_cache_write is None else per_m_cache_write
        parts = {
            "input": self.input / 1e6 * per_m_in,
            "output": self.output / 1e6 * per_m_out,
            "cache_read": self.cache_read / 1e6 * per_m_cache_read,
            "cache_write": self.cache_write / 1e6 * cw_rate,
        }
        return {**parts, "total": sum(parts.values()),
                "reasoning_surcharge": self.reasoning / 1e6 * per_m_out}


@dataclass
class Reading:
    """A scoped token reading: totals, the per-agent split, and `unavailable` — a reason
    string when the store could not be read, so a caller can say *why* it has no numbers
    instead of rendering a confident zero."""
    total: Usage = field(default_factory=Usage)
    by_agent: dict[str, Usage] = field(default_factory=dict)
    unavailable: str | None = None


def find_db(data_dir=None) -> Path | None:
    """opencode's session store, or None if it isn't where we expect."""
    base = Path(data_dir) if data_dir else _DEFAULT_DATA
    for name in _DB_NAMES:
        if (base / name).is_file():
            return base / name
    return None


def _connect(db: Path):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def usage_for(directory, *, db=None, data_dir=None) -> Reading:
    """Token usage for every opencode session that ran under `directory` (prefix match, so
    a run dir picks up its nested project dir too), split by agent.

    Returns a Reading with `unavailable` set — never raises — when the store is missing or
    its schema has moved: this is diagnostics riding alongside a benchmark, and a schema
    drift in someone else's database must not take the benchmark with it."""
    path = Path(db) if db else find_db(data_dir)
    if path is None:
        return Reading(unavailable=f"no opencode store found under {data_dir or _DEFAULT_DATA}")
    prefix = str(Path(directory).resolve())
    rows = []
    try:
        with _connect(path) as conn:
            for table in _SESSION_TABLES:
                have = {r[1] for r in conn.execute(f"pragma table_info({table})")}
                if not have:
                    continue  # this opencode generation never wrote one
                missing = {"directory", "agent", *_COLUMNS} - have
                if missing:
                    return Reading(unavailable=f"{path.name}: {table} table lacks "
                                               f"{sorted(missing)} (opencode schema changed?)")
                cols = ", ".join(f"sum(coalesce({c}, 0))" for c in _COLUMNS)
                rows += conn.execute(
                    f"select coalesce(agent, '(none)'), count(*), {cols}, "
                    f"{'sum(coalesce(cost, 0))' if 'cost' in have else '0'} "
                    f"from {table} where directory = ? or directory like ? "
                    f"group by 1", (prefix, prefix + os.sep + "%")).fetchall()
    except sqlite3.Error as e:
        return Reading(unavailable=f"{path.name}: {e}")
    if not rows and not _has_any_table(path):
        return Reading(unavailable=f"{path.name}: no session table (opencode schema changed?)")

    reading = Reading()
    for agent, n, ti, to, tr, tcr, tcw, cost in rows:
        u = Usage(sessions=n, input=ti, output=to, reasoning=tr,
                  cache_read=tcr, cache_write=tcw, cost=float(cost or 0))
        reading.by_agent[agent] = reading.by_agent.get(agent, Usage()) + u
        reading.total = reading.total + u
    return reading


def _has_any_table(path: Path) -> bool:
    try:
        with _connect(path) as conn:
            return any(conn.execute(f"pragma table_info({t})").fetchone() for t in _SESSION_TABLES)
    except sqlite3.Error:
        return False


def usage_for_batch(out_dir, *, db=None, data_dir=None) -> dict:
    """A whole batch: one Reading per `run-*` dir, plus the checking and grading workspaces
    (`check-ws`, `grade-ws`) kept separate. They are the instrument measuring play and belong
    in their own columns, never folded into what play cost."""
    out_dir = Path(out_dir)
    runs = {p.name: usage_for(p, db=db, data_dir=data_dir)
            for p in sorted(out_dir.glob("run-*")) if p.is_dir()}

    def ws(name):
        path = out_dir / name
        return usage_for(path, db=db, data_dir=data_dir) if path.is_dir() else Reading()
    return {"runs": runs, "checking": ws("check-ws"), "grading": ws("grade-ws"),
            "out_dir": str(out_dir)}


# ── render ───────────────────────────────────────────────────────────────────

def _row(label: str, u: Usage, width: int = 22) -> str:
    return (f"  {label[:width]:<{width}}{u.sessions:>6}{u.input:>12,}{u.output:>10,}"
            f"{u.reasoning:>10,}{u.cache_read:>14,}{u.cache_write:>10,}")


_HEAD = (f"  {'agent':<22}{'sess':>6}{'input':>12}{'output':>10}"
         f"{'reason':>10}{'cache read':>14}{'cache wr':>10}")


def format_tokens(batch: dict, *, prices: tuple[float, float, float] | None = None) -> str:
    """The token report: per-run totals with the per-agent split, grading kept separate,
    and — only when `prices` is given — what it would have cost at that rate card."""
    L = ["=" * 88,
         f"TOKEN USAGE — {batch['out_dir']}",
         "=" * 88]

    reasons = {r.unavailable for r in [*batch["runs"].values(), batch["checking"], batch["grading"]]
               if r.unavailable}
    if reasons:
        L += ["", "  (!) token data unavailable:"] + [f"      {r}" for r in sorted(reasons)]

    play = Usage()
    for name, reading in batch["runs"].items():
        if reading.unavailable:
            continue
        L += ["", f"── {name} " + "─" * max(0, 86 - len(name) - 4), _HEAD]
        for agent, u in sorted(reading.by_agent.items(), key=lambda kv: -kv[1].input):
            L.append(_row(agent, u))
        L.append("  " + "-" * 84)
        L.append(_row("run total", reading.total))
        play = play + reading.total

    checking, grading = batch["checking"].total, batch["grading"].total
    if checking.sessions:
        L += ["", "── checking (check-ws) " + "─" * 64, _HEAD, _row("checking total", checking)]
    if grading.sessions:
        L += ["", "── grading (grade-ws) " + "─" * 65, _HEAD, _row("grading total", grading)]

    everything = play + checking + grading
    scopes = (("play + reconcile", play), ("checking", checking), ("grading", grading),
              ("everything", everything))
    L += ["", "── batch total " + "─" * 72, _HEAD, *(_row(label, u) for label, u in scopes)]

    if prices:
        per_in, per_out, per_cr = prices
        L += ["", "── hypothetical cost " + "─" * 66,
              f"  at ${per_in:g}/M input · ${per_out:g}/M output · ${per_cr:g}/M cache read",
              ""]
        L.append(f"  {'scope':<22}{'input':>11}{'output':>11}{'cache read':>13}{'TOTAL':>11}")
        for label, u in scopes:
            p = u.priced(per_in, per_out, per_cr)
            L.append(f"  {label:<22}{'$%.4f' % p['input']:>11}{'$%.4f' % p['output']:>11}"
                     f"{'$%.4f' % p['cache_read']:>13}{'$%.4f' % p['total']:>11}")
        surcharge = everything.priced(per_in, per_out, per_cr)["reasoning_surcharge"]
        L += ["",
              f"  Reasoning tokens ({everything.reasoning:,}) are counted in `output` above.",
              f"  If your provider bills them on top instead, add ${surcharge:.4f}."]
        recorded = everything.cost
        L.append(f"  opencode recorded ${recorded:.4f} actually charged"
                 + (" (free tier)." if recorded == 0 else "."))

    L.append("=" * 88)
    return "\n".join(L)

# ── per session ─────────────────────────────────────────────────────────────
#
# One level down from the totals: the per-message rows opencode 2.x keeps in `session_message`.
# `--sessions` lists every session under a directory (wall and model time, steps, peak context,
# the skills it loaded); `--session N` prints one as a timeline — each brief or player message,
# each model step with its duration and tokens, its text and tool calls. A session the
# orchestrator's retry reverted (`Backend._revert_to`) has lost the reverted messages, so a
# failed attempt's steps don't appear, though its tokens still count in the totals above.

# A wait longer than this before a message is worth flagging: the player thinking, the
# orchestrator between stages, or a stall.
_GAP_S = 90


def _load(raw: str):
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return {}


def _clock(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%H:%M:%S") if ms else "--:--:--"


def _messages(conn, session_id: str) -> list[tuple[str, dict]]:
    return [(t, _load(d)) for t, d in conn.execute(
        "select type, data from session_message where session_id = ? order by seq",
        (session_id,))]


def _tools(msg: dict) -> list[tuple[str, dict]]:
    """(name, state) for each tool call in an assistant message. opencode stores a large
    state as a JSON string and a small one inline."""
    return [(c.get("name", "?"), _load(c.get("state")) or {})
            for c in msg.get("content") or [] if c.get("type") == "tool"]


def _step_tokens(msg: dict) -> tuple[int, int, int, int]:
    t = msg.get("tokens") or {}
    return (t.get("input", 0), (t.get("cache") or {}).get("read", 0),
            t.get("output", 0), t.get("reasoning", 0))


def _step_seconds(msg: dict) -> float:
    tm = msg.get("time") or {}
    return max(0, (tm.get("completed") or tm.get("created", 0)) - tm.get("created", 0)) / 1000


def _summary(conn, row) -> dict:
    sid, agent, title, created, updated, *tokens = row
    steps = secs = peak = errors = 0
    skills: list[str] = []
    for typ, msg in _messages(conn, sid):
        if typ != "assistant":
            continue
        steps += 1
        secs += _step_seconds(msg)
        inp, cache, _, _ = _step_tokens(msg)
        peak = max(peak, inp + cache)
        for name, state in _tools(msg):
            if state.get("status") == "error":
                errors += 1
            if name == "skill":
                skills.append((state.get("input") or {}).get("id")
                              or (state.get("input") or {}).get("name") or "?")
    return {"id": sid, "agent": agent or "(none)", "title": title, "created": created,
            "wall_s": (updated - created) / 1000, "model_s": secs, "steps": steps,
            "peak_context": peak, "tool_errors": errors, "skills": skills,
            "input": tokens[0], "output": tokens[1], "reasoning": tokens[2],
            "cache_read": tokens[3]}


def sessions_for(directory, *, db=None, data_dir=None) -> tuple[list[dict], str | None]:
    """Every opencode session under `directory` (prefix match, as `tokens` does), oldest
    first, summarised. Returns (sessions, reason) — `reason` set when the store can't be read."""
    path = Path(db) if db else find_db(data_dir)
    if path is None:
        return [], "no opencode store found"
    prefix = str(Path(directory).resolve())
    try:
        with _connect(path) as conn:
            if not conn.execute("pragma table_info(session_message)").fetchone():
                return [], f"{path.name} has no session_message table (opencode 1.x store?)"
            rows = conn.execute(
                "select id, agent, title, time_created, time_updated, tokens_input, "
                "tokens_output, tokens_reasoning, tokens_cache_read from session_v2 "
                "where directory = ? or directory like ? order by time_created",
                (prefix, prefix + os.sep + "%")).fetchall()
            return [_summary(conn, r) for r in rows], None
    except sqlite3.Error as e:
        return [], f"{path.name}: {e}"


def format_sessions(directory, sessions: list[dict]) -> str:
    L = [f"SESSIONS — {directory}", "",
         f"  {'#':>3}  {'start':<8}  {'agent':<17} {'title':<26}{'wall':>7}{'model':>7}"
         f"{'steps':>6}{'peak ctx':>10}{'cache read':>12}{'reason':>9}{'err':>5}"]
    for i, s in enumerate(sessions, 1):
        L.append(f"  {i:>3}  {_clock(s['created']):<8}  {s['agent'][:17]:<17} "
                 f"{(s['title'] or '')[:25]:<26}{s['wall_s'] / 60:>6.1f}m{s['model_s'] / 60:>6.1f}m"
                 f"{s['steps']:>6}{s['peak_context']:>10,}{s['cache_read']:>12,}"
                 f"{s['reasoning']:>9,}{s['tool_errors']:>5}")
        if s["skills"]:
            counts: dict[str, int] = {}
            for k in s["skills"]:
                counts[k] = counts.get(k, 0) + 1
            L.append("       skills: " + ", ".join(
                k + (f" ×{n}" if n > 1 else "") for k, n in counts.items()))
    L += ["", "  wall = first message to last; model = time spent in model steps.",
          "  `--session N` prints one as a timeline."]
    return "\n".join(L)


def _tool_line(name: str, state: dict) -> str:
    inp = state.get("input") or {}
    out = "".join(c.get("text", "") for c in state.get("content") or [] if isinstance(c, dict))
    if name == "skill":
        what = inp.get("id") or inp.get("name") or ""
    elif name in ("write", "edit", "patch", "apply_patch"):
        what = inp.get("path") or inp.get("filePath") or ""
        if not what and isinstance(inp.get("patchText"), str):
            what = " ".join(l.split(":", 1)[1].strip() for l in inp["patchText"].splitlines()
                            if l.startswith("*** ") and ":" in l and "File" in l)
    else:
        what = json.dumps(inp, ensure_ascii=False)
        what = what if len(what) <= 160 else what[:157] + "..."
    status = state.get("status", "?")
    flag = "  ✗ " + status if status != "completed" else ""
    return f"     → {name} {what}  [{len(out):,} chars]{flag}"


def format_timeline(session_id: str, *, db=None, data_dir=None, reasoning: bool = False,
                    width: int = 600) -> str:
    """One session as a readable timeline. `reasoning` adds the model's reasoning headings;
    `width` caps each text block (0 for no cap)."""
    path = Path(db) if db else find_db(data_dir)
    if path is None:
        return "no opencode store found"

    def cap(text: str) -> str:
        text = text.strip()
        return text if not width or len(text) <= width else text[:width] + f" …[{len(text):,} chars]"

    L: list[str] = []
    last_end = None
    step = 0
    with _connect(path) as conn:
        for typ, msg in _messages(conn, session_id):
            created = (msg.get("time") or {}).get("created")
            if last_end and created and (created - last_end) / 1000 > _GAP_S:
                L.append(f"  ·· {(created - last_end) / 60000:.1f} min idle ··")
            if typ == "user":
                L += ["", f"━━ {_clock(created)}  brief / player", cap(msg.get("text", "")), ""]
                last_end = created
            elif typ == "assistant":
                step += 1
                inp, cache, out, rs = _step_tokens(msg)
                L.append(f"── step {step}  {_clock(created)}  {_step_seconds(msg):.0f}s  "
                         f"ctx {inp + cache:,}  out {out:,}  reasoning {rs:,}")
                for c in msg.get("content") or []:
                    kind = c.get("type")
                    if kind == "reasoning" and reasoning and c.get("text", "").strip():
                        L.append("     · " + c["text"].strip().splitlines()[0][:120])
                    elif kind == "text" and c.get("text", "").strip():
                        L.append("     " + cap(c["text"]).replace("\n", "\n     "))
                    elif kind == "tool":
                        L.append(_tool_line(c.get("name", "?"), _load(c.get("state")) or {}))
                last_end = (msg.get("time") or {}).get("completed") or created
            elif typ in ("agent-switched", "model-switched"):
                detail = msg.get("agent") or (msg.get("model") or {}).get("id", "")
                L.append(f"  ({typ}: {detail})")
    return "\n".join(L) if L else f"no messages for session {session_id}"


def resolve(sessions: list[dict], ref: str) -> str | None:
    """A session from the list by its 1-based number there, or by id prefix."""
    if ref.isdigit() and 1 <= int(ref) <= len(sessions):
        return sessions[int(ref) - 1]["id"]
    hits = [s["id"] for s in sessions if s["id"].startswith(ref)]
    return hits[0] if len(hits) == 1 else None
