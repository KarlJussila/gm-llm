"""
`bench tokens` — what a run actually cost, in tokens (BENCHMARK.md B2, instrument health).

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

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

# opencode's store. `OPENCODE_DATA` overrides, matching opencode's own env handling; the
# `-local` variant is the fallback some installs write instead.
_DEFAULT_DATA = Path(os.environ.get("OPENCODE_DATA")
                     or (Path.home() / ".local" / "share" / "opencode"))
_DB_NAMES = ("opencode.db", "opencode-local.db")

_COLUMNS = ("tokens_input", "tokens_output", "tokens_reasoning",
            "tokens_cache_read", "tokens_cache_write")


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
    try:
        with _connect(path) as conn:
            have = {r[1] for r in conn.execute("pragma table_info(session)")}
            missing = {"directory", "agent", *_COLUMNS} - have
            if missing:
                return Reading(unavailable=f"{path.name}: session table lacks {sorted(missing)} "
                                           f"(opencode schema changed?)")
            cols = ", ".join(f"sum(coalesce({c}, 0))" for c in _COLUMNS)
            has_cost = "cost" in have
            rows = conn.execute(
                f"select coalesce(agent, '(none)'), count(*), {cols}, "
                f"{'sum(coalesce(cost, 0))' if has_cost else '0'} "
                f"from session where directory = ? or directory like ? "
                f"group by 1", (prefix, prefix + os.sep + "%")).fetchall()
    except sqlite3.Error as e:
        return Reading(unavailable=f"{path.name}: {e}")

    reading = Reading()
    for agent, n, ti, to, tr, tcr, tcw, cost in rows:
        u = Usage(sessions=n, input=ti, output=to, reasoning=tr,
                  cache_read=tcr, cache_write=tcw, cost=float(cost or 0))
        reading.by_agent[agent] = u
        reading.total = reading.total + u
    return reading


def usage_for_batch(out_dir, *, db=None, data_dir=None) -> dict:
    """A whole batch: one Reading per `run-*` dir, plus the grading workspace (`grade-ws`)
    kept separate. Grading is the instrument scoring itself and belongs in its own column,
    never folded into what play cost."""
    out_dir = Path(out_dir)
    runs = {p.name: usage_for(p, db=db, data_dir=data_dir)
            for p in sorted(out_dir.glob("run-*")) if p.is_dir()}
    ws = out_dir / "grade-ws"
    return {"runs": runs,
            "grading": usage_for(ws, db=db, data_dir=data_dir) if ws.is_dir() else Reading(),
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

    reasons = {r.unavailable for r in list(batch["runs"].values()) + [batch["grading"]]
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

    grading = batch["grading"].total
    if grading.sessions:
        L += ["", "── grading (grade-ws) " + "─" * 65, _HEAD, _row("grading total", grading)]

    L += ["", "── batch total " + "─" * 72, _HEAD,
          _row("play + reconcile", play), _row("grading", grading),
          _row("everything", play + grading)]

    if prices:
        per_in, per_out, per_cr = prices
        L += ["", "── hypothetical cost " + "─" * 66,
              f"  at ${per_in:g}/M input · ${per_out:g}/M output · ${per_cr:g}/M cache read",
              ""]
        L.append(f"  {'scope':<22}{'input':>11}{'output':>11}{'cache read':>13}{'TOTAL':>11}")
        for label, u in (("play + reconcile", play), ("grading", grading),
                         ("everything", play + grading)):
            p = u.priced(per_in, per_out, per_cr)
            L.append(f"  {label:<22}{'$%.4f' % p['input']:>11}{'$%.4f' % p['output']:>11}"
                     f"{'$%.4f' % p['cache_read']:>13}{'$%.4f' % p['total']:>11}")
        surcharge = (play + grading).priced(per_in, per_out, per_cr)["reasoning_surcharge"]
        L += ["",
              f"  Reasoning tokens ({(play + grading).reasoning:,}) are counted in `output` above.",
              f"  If your provider bills them on top instead, add ${surcharge:.4f}."]
        recorded = play.cost + grading.cost
        L.append(f"  opencode recorded ${recorded:.4f} actually charged"
                 + (" (free tier)." if recorded == 0 else "."))

    L.append("=" * 88)
    return "\n".join(L)
