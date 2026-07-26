"""
The `bench report` engine — archive + grades → summary (BENCHMARK.md B2).

Pure aggregation: no model calls, no network. It reads a batch out-dir (the `batch.jsonl`
manifest B1 writes, each run's score archive, and the `grades-*.jsonl` B2 writes beside
it) and rolls it up per-run and per-batch. Everything the report shows is re-derived from
the raw archive and the derived grades — nothing is judged here.

Two things this module is opinionated about, both from the measurement methodology:

  * **Instrument health is prominent.** The `defaulted`-verdict rate (a checker that gave
    no usable verdict, so the content passed by default) rides at the top of every run and
    the batch: a checker not doing its job must never read as the subject improving. The
    ungraded count (the grader's own misses) sits beside it.

  * **Mismatched conditions are impossible to miss.** Each run carries a condition
    signature (fixture, tier, turn cap, per-agent model+temperature) from its `conditions`
    event. A batch whose runs don't all share one signature is flagged loudly at the very
    top — a comparison across mixed conditions should be impossible to make by accident.

The score model lives here too (`score_violations`): dedup'd violations cost penalty points
by severity, the points normalize by run length into a rate, and the rate maps to a 0–100
integrity score plus per-dimension subscores. It is reported *beside* the severity vector,
never instead of it — BENCHMARK.md's "distributions, not single numbers" is the standing
constraint, and a composite that hides which dimension moved is worse than no composite.

Distributions, not points: scores, violation counts, turns-to-wrap, and the rates are
reported as min/median/max across the runs, not just a mean. Stdlib only.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from .grade import RUBRIC, unmanifested_archives

# Display order for the rubric's severity ladder; any off-rubric label the grader emitted
# is appended after these so it can never be silently dropped from a count.
_SEVERITY_ORDER = ["trivial", "minor", "major", "critical"]

# ── the score model ──────────────────────────────────────────────────────────
#
# Penalty points per dedup'd violation. Steep on purpose: a critical is worth three majors,
# because a spoiled `[hidden]` reveal costs the campaign something a handful of recoverable
# contradictions doesn't. A trivial registers without moving the number much.
_PENALTY = {"trivial": 0.25, "minor": 1.0, "major": 4.0, "critical": 12.0}

# Points per graded unit at which a run scores 0 — "unusable": averaging one major every
# other turn. This is the score's one arbitrary constant, a display calibration rather than
# a measurement; the rate underneath it is the real quantity. Retune once B3 banks a
# distribution and we know where tier 0 actually lands.
_FLOOR_RATE = 2.0

# The rubric's 9 categories, collapsed into the dimensions a subscore is reported on. Every
# category maps to exactly one; an off-rubric label falls through to "other" so it stays
# visible in the total instead of scoring free.
_DIMENSIONS = {
    "canon_fidelity":         ("canon-contradiction", "fabrication"),
    "information_discipline": ("spoiler-leak", "npc-provenance", "metagame-leak"),
    "player_agency":          ("agency", "pacing"),
    "mechanical_integrity":   ("dice-and-uncertainty", "rules-error"),
    "record_integrity":       ("record-integrity",),
}
_DIM_OF = {cat: dim for dim, cats in _DIMENSIONS.items() for cat in cats}
_DIM_LABEL = {
    "canon_fidelity": "canon fidelity", "information_discipline": "information discipline",
    "player_agency": "player agency", "mechanical_integrity": "mechanical integrity",
    "record_integrity": "record integrity", "other": "other (off-rubric)",
}


def _score(penalty: float, units: int) -> float | None:
    """Penalty points → a 0–100 score, normalized by run length so a 30-turn run and a
    50-turn one compare. `None` when there is nothing to divide by."""
    if not units:
        return None
    return 100.0 * max(0.0, 1.0 - (penalty / units) / _FLOOR_RATE)


def score_violations(scored: list[dict], units: int) -> dict:
    """The score model over one run's *dedup'd* graded findings.

    Each violation costs `_PENALTY[severity]`; the points sum, divide by graded units
    (turns + stage gates) into a rate, and map to 0–100. Subscores run the same formula over
    one dimension's violations against the *same* denominator — so the composite is computed
    from the total penalty, never averaged from the subscores (averaging would divide a
    catastrophic agency failure by five). That makes the deficits decompose additively:
    a composite of 33 has lost 67 points, split exactly across the dimensions, until a
    subscore clamps at 0."""
    per_dim: dict[str, float] = {d: 0.0 for d in _DIMENSIONS}
    counts: dict[str, int] = {d: 0 for d in _DIMENSIONS}
    total = 0.0
    unweighted = 0
    for g in scored:
        if g.get("ungraded") or g.get("duplicate_of"):
            continue
        pts = _PENALTY.get(g.get("severity"), 0.0)
        if g.get("severity") not in _PENALTY:
            unweighted += 1
        dim = _DIM_OF.get(g.get("category"), "other")
        per_dim[dim] = per_dim.get(dim, 0.0) + pts
        counts[dim] = counts.get(dim, 0) + 1
        total += pts
    return {
        "units": units,
        "penalty": round(total, 3),
        "rate": round(total / units, 4) if units else None,
        "score": _score(total, units),
        "dimensions": {d: {"penalty": round(p, 3), "violations": counts.get(d, 0),
                           "score": _score(p, units)}
                       for d, p in per_dim.items()},
        "off_rubric_severities": unweighted,
    }


def _read_events(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _dist(values) -> dict | None:
    """min / median / max / mean over the non-None values, with the count. None if empty —
    a distribution of nothing is not a distribution."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"min": min(vals), "median": statistics.median(vals), "max": max(vals),
            "mean": statistics.mean(vals), "n": len(vals)}


def _sev_sorted(labels) -> list[str]:
    known = [s for s in _SEVERITY_ORDER if s in labels]
    extra = sorted(l for l in labels if l not in _SEVERITY_ORDER)
    return known + extra


# ── per-run ──────────────────────────────────────────────────────────────────

def _conditions(events: list[dict]) -> dict:
    for e in events:
        if e.get("event") == "conditions":
            return e
    return {}


def _condition_signature(cond: dict) -> dict:
    """The axes a cross-run comparison must hold constant. Two runs are the same condition
    iff these match; the report flags a batch that mixes them."""
    fixture = cond.get("fixture") or {}
    agents = cond.get("agents") or {}
    return {
        "fixture": fixture.get("id"),
        "tier": cond.get("tier"),
        "turn_cap": cond.get("turn_cap"),
        "agents": {name: (a.get("model"), a.get("temperature")) for name, a in sorted(agents.items())},
    }


def summarize_run(events: list[dict], grades: list[dict]) -> dict:
    """One run's numbers, all re-derived: outcome, turns, correction rate, the prominent
    defaulted-verdict rate, violation counts by severity (raw and dedup'd), ungraded count,
    stage-gate outcomes, and context growth if the archive carried it. `grades` is the
    per-finding grade lines (header dropped); an empty list means the run wasn't graded."""
    turns = [e for e in events if e.get("event") == "turn"]
    stages = [e for e in events if e.get("event") == "stage"]
    capped = any(e.get("event") == "cap" for e in events)

    # outcome / turns-to-wrap
    complete = bool(turns) and bool(turns[-1].get("session_complete"))
    outcome = "cap" if capped else ("complete" if complete else "unwrapped")
    turns_to_wrap = len(turns) if outcome == "complete" else None

    # correction rate
    corrected = sum(1 for t in turns if t.get("corrected"))

    # defaulted-verdict rate — instrument health, over every runtime and stage verdict
    all_verdicts: list[dict] = []
    for t in turns:
        all_verdicts += t.get("verdicts", [])
    for s in stages:
        if s.get("verdict"):
            all_verdicts.append(s["verdict"])
    defaulted = sum(1 for v in all_verdicts if v.get("defaulted"))

    # stage-gate outcomes
    stage_outcomes = []
    for s in stages:
        v = s.get("verdict") or {}
        if s.get("stage") == "lint":
            passed = not s.get("incomplete")
        else:
            passed = bool(v.get("passed"))
        stage_outcomes.append({"stage": s.get("stage"), "session": s.get("session"),
                               "passed": passed, "corrected": bool(s.get("corrected")),
                               "defaulted": bool(v.get("defaulted"))})

    # violations by severity, raw (every graded finding) and dedup'd (drop duplicate_of)
    scored = [g for g in grades if not g.get("ungraded")]
    ungraded = sum(1 for g in grades if g.get("ungraded"))
    raw_by_sev: dict[str, int] = {}
    dedup_by_sev: dict[str, int] = {}
    for g in scored:
        sev = g.get("severity", "?")
        raw_by_sev[sev] = raw_by_sev.get(sev, 0) + 1
        if not g.get("duplicate_of"):
            dedup_by_sev[sev] = dedup_by_sev.get(sev, 0) + 1

    # context growth (first → last turn that carried a context reading)
    ctx = [t["context"]["tokens"] for t in turns if t.get("context")]
    context_growth = ({"first": ctx[0], "last": ctx[-1], "delta": ctx[-1] - ctx[0]}
                      if len(ctx) >= 2 else None)

    # the score: penalty points over graded units (every turn and stage gate that could
    # have produced a violation), 0–100 plus per-dimension subscores
    score = score_violations(scored, len(turns) + len(stages)) if grades else None

    return {
        "run_id": next((e.get("run_id") for e in events if e.get("event") == "run"), None),
        "conditions": _conditions(events),
        "outcome": outcome,
        "score": score,
        "turns": len(turns),
        "turns_to_wrap": turns_to_wrap,
        "corrected_turns": corrected,
        "correction_rate": (corrected / len(turns)) if turns else None,
        "verdicts_total": len(all_verdicts),
        "defaulted_verdicts": defaulted,
        "defaulted_rate": (defaulted / len(all_verdicts)) if all_verdicts else None,
        "violations_raw": len(scored),
        "violations_dedup": sum(dedup_by_sev.values()),
        "by_severity_raw": raw_by_sev,
        "by_severity_dedup": dedup_by_sev,
        "ungraded": ungraded,
        "graded": bool(grades),
        "stage_outcomes": stage_outcomes,
        "context_growth": context_growth,
    }


# ── batch ────────────────────────────────────────────────────────────────────

def _grades_for(archive_path: Path) -> list[dict]:
    """The per-finding grade lines for a run, from `grades-<run_id>-<rubric>.jsonl` beside
    its archive (the primary pass — the `-b` double pass is not a report input). Empty if
    the run hasn't been graded."""
    run_id = archive_path.stem.replace("archive-", "")
    grades_path = archive_path.parent / f"grades-{run_id}-{RUBRIC}.jsonl"
    if not grades_path.is_file():
        return []
    return [e for e in _read_events(grades_path) if e.get("event") != "grades"]


def summarize_batch(out_dir) -> dict:
    """Roll a whole batch up from its `batch.jsonl` + archives + grades. Per-run summaries,
    the mixed-conditions check, and batch distributions (violation counts, turns-to-wrap,
    defaulted rate) — min/median/max across runs, never a lone mean."""
    out_dir = Path(out_dir)
    manifest = out_dir / "batch.jsonl"
    runs: list[dict] = []
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            arc = rec.get("archive")
            if not arc:
                runs.append({"run_id": rec.get("run"), "outcome": rec.get("outcome"),
                             "turns": rec.get("turns", 0), "graded": False,
                             "conditions": {}, "no_archive": True})
                continue
            archive_path = out_dir / arc
            events = _read_events(archive_path)
            runs.append(summarize_run(events, _grades_for(archive_path)))

    # mixed-conditions check
    sigs = [_condition_signature(r.get("conditions") or {}) for r in runs if not r.get("no_archive")]
    distinct = []
    for s in sigs:
        if s not in distinct:
            distinct.append(s)
    mixed = len(distinct) > 1

    graded_runs = [r for r in runs if r.get("graded")]
    by_sev_raw: dict[str, int] = {}
    by_sev_dedup: dict[str, int] = {}
    for r in graded_runs:
        for sev, n in r["by_severity_raw"].items():
            by_sev_raw[sev] = by_sev_raw.get(sev, 0) + n
        for sev, n in r["by_severity_dedup"].items():
            by_sev_dedup[sev] = by_sev_dedup.get(sev, 0) + n

    # Score distributions across the batch: the composite, and each dimension separately —
    # a tier that fixes canon fidelity while regressing on agency must not read as flat.
    scores = [r["score"] for r in graded_runs if r.get("score")]
    dim_dists = {d: _dist([s["dimensions"][d]["score"] for s in scores]) for d in _DIMENSIONS}

    return {
        "out_dir": str(out_dir),
        "rubric": RUBRIC,
        "n_runs": len(runs),
        # archives on disk the manifest doesn't point at: their violations are missing from
        # every number below, and missing data must never render as a clean run
        "unmanifested": [str(p.relative_to(out_dir)) for p in unmanifested_archives(out_dir)],
        "score": _dist([s["score"] for s in scores]),
        "penalty_rate": _dist([s["rate"] for s in scores]),
        "dimension_scores": dim_dists,
        "dimension_violations": {d: sum(s["dimensions"][d]["violations"] for s in scores)
                                 for d in _DIMENSIONS},
        "mixed_conditions": mixed,
        "conditions": distinct,
        "outcomes": {o: sum(1 for r in runs if r.get("outcome") == o)
                     for o in sorted({r.get("outcome") for r in runs if r.get("outcome")})},
        "violations_raw": _dist([r["violations_raw"] for r in graded_runs]),
        "violations_dedup": _dist([r["violations_dedup"] for r in graded_runs]),
        "turns_to_wrap": _dist([r.get("turns_to_wrap") for r in runs]),
        "correction_rate": _dist([r.get("correction_rate") for r in runs if r.get("correction_rate") is not None]),
        "defaulted_rate": _dist([r.get("defaulted_rate") for r in runs if r.get("defaulted_rate") is not None]),
        "defaulted_total": sum(r.get("defaulted_verdicts", 0) for r in runs if not r.get("no_archive")),
        "ungraded_total": sum(r.get("ungraded", 0) for r in graded_runs),
        "by_severity_raw": by_sev_raw,
        "by_severity_dedup": by_sev_dedup,
        "n_graded": len(graded_runs),
        "runs": runs,
    }


# ── plain-text render ────────────────────────────────────────────────────────

def _fmt_dist(d: dict | None, pct: bool = False, dp: int | None = None) -> str:
    """min/median/max/mean of a distribution. `dp` fixes the decimal places — scores and
    rates carry more float precision than anyone should read off a report."""
    if not d:
        return "—"
    def f(v):
        if pct:
            return f"{v:.0%}"
        if dp is not None and isinstance(v, (int, float)):
            return f"{v:.{dp}f}"
        return f"{v:g}" if isinstance(v, float) else str(v)
    return f"min {f(d['min'])} · median {f(d['median'])} · max {f(d['max'])} · mean {f(d['mean'])} (n={d['n']})"


def _fmt_sig(sig: dict) -> str:
    agents = "; ".join(f"{name}={model}@{temp}" for name, (model, temp) in sig.get("agents", {}).items())
    return (f"fixture={sig.get('fixture')} tier={sig.get('tier')} "
            f"turn_cap={sig.get('turn_cap')} · {agents}")


def format_report(batch: dict) -> str:
    """The one-page plain-text report. The mixed-conditions banner (if any) leads, then
    instrument health, then the batch distributions, then a per-run table."""
    L: list[str] = []
    L.append("=" * 78)
    L.append(f"BENCHMARK REPORT — {batch['out_dir']}  ·  rubric {batch['rubric']}  ·  {batch['n_runs']} run(s)")
    L.append("=" * 78)

    if batch["mixed_conditions"]:
        L.append("")
        L.append("!!! MIXED CONDITIONS — DO NOT COMPARE THESE RUNS AS ONE BATCH !!!")
        L.append("The runs below do not share one condition signature. Scores across them")
        L.append("are not comparable. Distinct conditions found:")
        for i, sig in enumerate(batch["conditions"], 1):
            L.append(f"  [{i}] {_fmt_sig(sig)}")
    elif batch["conditions"]:
        L.append(f"Condition: {_fmt_sig(batch['conditions'][0])}")

    # Instrument health first — a checker not doing its job must never read as improvement.
    L.append("")
    L.append("── Instrument health ──────────────────────────────────────────────────────")
    L.append(f"  defaulted-verdict rate : {_fmt_dist(batch['defaulted_rate'], pct=True)}")
    L.append(f"  defaulted verdicts     : {batch['defaulted_total']} total across the batch")
    L.append(f"  ungraded findings      : {batch['ungraded_total']} total "
             f"({batch['n_graded']}/{batch['n_runs']} run(s) graded)")
    if batch["unmanifested"]:
        L.append(f"  !! UNMANIFESTED ARCHIVES: {len(batch['unmanifested'])} — scored as if they "
                 f"never played:")
        for rel in batch["unmanifested"]:
            L.append(f"       {rel}")
        L.append("     Fold them into their run's archive or add them to batch.jsonl; until")
        L.append("     then every number below understates the violations.")

    L.append("")
    L.append("── Score ───────────────────────────────────────────────────────────────────")
    if batch["score"]:
        L.append(f"  INTEGRITY SCORE        : {_fmt_dist(batch['score'], dp=1)}")
        L.append(f"  penalty rate (pts/unit): {_fmt_dist(batch['penalty_rate'], dp=2)}")
        L.append("  by dimension (score · violations across the batch):")
        for d in _DIMENSIONS:
            dist = batch["dimension_scores"].get(d)
            n = batch["dimension_violations"].get(d, 0)
            L.append(f"    {_DIM_LABEL[d]:<24} {_fmt_dist(dist, dp=1):<62} {n:>3} viol")
        L.append(f"  (weights {', '.join(f'{s}={p:g}' for s, p in _PENALTY.items())}; "
                 f"0 at {_FLOOR_RATE:g} pts/unit)")
    else:
        L.append("  (no graded runs — score needs `bench grade` first)")

    L.append("")
    L.append("── Violations ──────────────────────────────────────────────────────────────")
    L.append(f"  per run, raw           : {_fmt_dist(batch['violations_raw'])}")
    L.append(f"  per run, dedup'd       : {_fmt_dist(batch['violations_dedup'])}")
    if batch["by_severity_raw"]:
        for sev in _sev_sorted(set(batch["by_severity_raw"]) | set(batch["by_severity_dedup"])):
            raw = batch["by_severity_raw"].get(sev, 0)
            ded = batch["by_severity_dedup"].get(sev, 0)
            L.append(f"    {sev:<10} raw {raw:>3}   dedup'd {ded:>3}")
    else:
        L.append("    (no graded violations)")

    L.append("")
    L.append("── Play signals ────────────────────────────────────────────────────────────")
    L.append(f"  turns-to-wrap          : {_fmt_dist(batch['turns_to_wrap'])}")
    L.append(f"  correction rate        : {_fmt_dist(batch['correction_rate'], pct=True)}")
    outc = "  ".join(f"{o}={n}" for o, n in batch["outcomes"].items())
    L.append(f"  session close          : {outc or '—'}")

    L.append("")
    L.append("── Per run ─────────────────────────────────────────────────────────────────")
    L.append(f"  {'run':<20} {'outcome':<10} {'turns':>5} {'score':>6} {'viol(raw/ded)':>14} "
             f"{'corr':>5} {'dflt':>5} {'ungr':>5}")
    for r in batch["runs"]:
        if r.get("no_archive"):
            L.append(f"  {str(r.get('run_id'))[:20]:<20} {str(r.get('outcome'))[:10]:<10} "
                     f"{r.get('turns', 0):>5} {'—':>6} {'—':>14} {'—':>5} {'—':>5} {'—':>5}")
            continue
        viol = f"{r['violations_raw']}/{r['violations_dedup']}" if r.get("graded") else "—"
        sc = r.get("score") or {}
        score = f"{sc['score']:.0f}" if sc.get("score") is not None else "—"
        corr = str(r.get("corrected_turns", "—"))
        dflt = str(r.get("defaulted_verdicts", "—"))
        ungr = str(r.get("ungraded", "—")) if r.get("graded") else "—"
        L.append(f"  {str(r.get('run_id'))[:20]:<20} {str(r.get('outcome'))[:10]:<10} "
                 f"{r.get('turns', 0):>5} {score:>6} {viol:>14} {corr:>5} {dflt:>5} {ungr:>5}")

    L.append("=" * 78)
    return "\n".join(L)
