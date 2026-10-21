"""
The `bench report` engine — archive + grades → summary (design/benchmark.md B2).

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
    signature (fixture, tier, turn cap, per-agent model and variant, the subagents mode) from its `conditions`
    event. A batch whose runs don't all share one signature is flagged loudly at the very
    top — a comparison across mixed conditions should be impossible to make by accident.

The score model lives here too (`score_violations`): dedup'd violations cost penalty points
by severity, the points normalize by run length into a rate, and the rate maps to a 0–100
integrity score plus per-dimension subscores. It is reported *beside* the severity vector,
never instead of it — design/benchmark.md's "distributions, not single numbers" is the standing
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

# Below this many violations batch-wide, a dimension subscore is built on so few severity
# labels that grader noise dominates it. Measured, not guessed: severity labels reproduce at
# roughly 80% across independent grading passes, and disagreement averages out as 1/√(findings)
# — ~20% of the subtotal over 5 findings against ~6% over 15. A composite pooling 13–22
# findings survives that; a subscore over one or two does not, and the report says so rather
# than printing a decimal point that means nothing.
_THIN_DIMENSION = 10

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


# Two-sided 95% critical values of Student's t by degrees of freedom (n-1). A batch estimates
# its own spread from the same handful of runs it is averaging, so the interval has to pay for
# not knowing the true spread — that surcharge is what t is, and it is *large* at the batch
# sizes this benchmark can afford: 2.776 at n=5 against the 1.960 a normal would use, a 42%
# wider interval. Using 1.960 here would report a precision the batch does not have.
# Table rather than a dependency: the repo is stdlib-only and this is nine significant rows.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
        9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
        23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
        30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}
_T95_INF = 1.960


def _t95(df: int) -> float:
    """The 95% two-sided t multiplier for `df` degrees of freedom — the exact row when the
    table has it, otherwise the next row down (conservative: a wider interval, never a
    narrower one than the truth)."""
    if df in _T95:
        return _T95[df]
    below = [k for k in _T95 if k < df]
    return _T95[max(below)] if below and df < 120 else _T95_INF


def mean_ci95(values) -> float | None:
    """Half-width of the 95% confidence interval on the mean: `t(n-1) · sd / √n`.

    Read it as "if this batch were re-run, the mean would land within ±this of the reported
    one 19 times out of 20" — the honest error bar on a batch score. `None` below n=2, where
    there is no spread to estimate and therefore no interval; a single run reports a number
    with no error bar rather than an error bar of zero.

    Assumes the runs are independent and roughly normal. Independence holds by construction
    (each run is a fresh project from the template). Normality is the shakier half at n=5 and
    the interval is approximate because of it — but the failure mode is a slightly wrong
    width, not a wrong conclusion, and the alternative at this n is no error bar at all."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    return _t95(len(vals) - 1) * statistics.stdev(vals) / len(vals) ** 0.5


def resolution95(values) -> float | None:
    """The smallest difference in means two batches *this size* could tell apart — the
    question a baseline actually has to answer, since its job is to catch a change.

    `(t(2n-2) + 0.84) · sd · √(2/n)`, the standard two-sample size formula at 95% confidence
    and 80% power (0.84 is the one-sided normal quantile for 80%). Approximate, and worth
    reading as an order of magnitude: a change smaller than this is invisible to a comparison
    of two batches, however carefully the prose was edited."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    n = len(vals)
    return (_t95(2 * n - 2) + 0.84) * statistics.stdev(vals) * (2 / n) ** 0.5


def _dist(values) -> dict | None:
    """min / median / max / mean over the non-None values, with the count, plus the 95%
    confidence interval on that mean and the difference a batch this size could resolve.
    None if empty — a distribution of nothing is not a distribution."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"min": min(vals), "median": statistics.median(vals), "max": max(vals),
            "mean": statistics.mean(vals), "n": len(vals),
            "ci95": mean_ci95(vals), "resolution95": resolution95(vals)}


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
    """The axes a cross-run comparison must hold constant, plus `turn_cap` for display.
    Two runs are the same condition iff their `_identity` matches; the report flags a batch
    that mixes them."""
    fixture = cond.get("fixture") or {}
    agents = cond.get("agents") or {}
    return {
        "fixture": fixture.get("id"),
        "tier": cond.get("tier"),
        "turn_cap": cond.get("turn_cap"),
        "agents": {name: (a.get("model"), a.get("variant")) for name, a in sorted(agents.items())},
        "subagents": cond.get("subagents"),
        # The prompts are the tier-0 subject, so a batch that mixes prose versions is mixing
        # conditions however well the models and fixture match. Archives written before the
        # fingerprint existed carry None and still pool with each other.
        "prompts": (cond.get("prompts") or {}).get("sha256"),
    }


def _identity(sig: dict) -> dict:
    """The comparable part of a signature — everything except `turn_cap`.

    The cap is a safety net, not a condition: it reaches no prompt (it lives entirely as a
    loop bound in `bench/runner.py`) and the wrap nudge keys off opencode's context
    threshold, not the cap. A run that never reaches it played exactly as it would have
    under any larger cap, so two such runs are the same condition however the caps were
    configured. What *is* a different condition is a run the cap actually bound: truncated
    session, reconcile skipped, no stage findings — and `outcome == "cap"` reports that
    directly, which is the honest place to catch it."""
    return {k: v for k, v in sig.items() if k != "turn_cap"}


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

def _grades_path(archive_path: Path) -> Path:
    """Where a run's primary grades live: `grades-<run_id>-<rubric>.jsonl` beside its
    archive (the `-b` double pass is not a report input)."""
    run_id = archive_path.stem.replace("archive-", "")
    return archive_path.parent / f"grades-{run_id}-{RUBRIC}.jsonl"


def _grades_for(archive_path: Path) -> list[dict]:
    """The per-finding grade lines for a run. Empty if the run hasn't been graded."""
    grades_path = _grades_path(archive_path)
    if not grades_path.is_file():
        return []
    return [e for e in _read_events(grades_path) if e.get("event") != "grades"]


def _grading_signature(archive_path: Path) -> dict | None:
    """Which grading instrument produced this run's grades, from the grades header: the
    rubric label, the instrument fingerprint, and the grader model/temperature.

    Grades are only comparable to grades taken the same way, and the rubric *label* does not
    move when the prose under it is rewritten in place — which has already happened once
    under `v1`. So the hash `grade.instrument_fingerprint` stamps is the part that actually
    separates two instruments; the label is kept alongside it for reading. `None` when the
    run is ungraded (it contributes no grades to disagree about). A header from before the
    fingerprint existed reports `sha256: None` and pools with its own kind, the same
    grandfathering `_condition_signature` gives pre-fingerprint archives."""
    grades_path = _grades_path(archive_path)
    if not grades_path.is_file():
        return None
    try:
        header = _read_events(grades_path)[0]
    except (OSError, ValueError, IndexError):
        return None
    grader = header.get("grader") or {}
    return {"rubric": header.get("rubric"),
            "sha256": (header.get("instrument") or {}).get("sha256"),
            "grader": (grader.get("model"), grader.get("temperature"))}


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
            summary = summarize_run(events, _grades_for(archive_path))
            summary["grading"] = _grading_signature(archive_path)
            runs.append(summary)

    # mixed-conditions check
    sigs = [_condition_signature(r.get("conditions") or {}) for r in runs if not r.get("no_archive")]
    distinct, seen = [], []
    for s in sigs:
        if _identity(s) not in seen:      # one representative sig per distinct condition
            seen.append(_identity(s))
            distinct.append(s)
    mixed = len(distinct) > 1
    capped = [r.get("run_id") for r in runs if r.get("outcome") == "cap"]

    # The same check one level down, on the instrument rather than the subject: two runs
    # scored by different rubric prose are no more comparable than two runs played under
    # different prompts, and until the fingerprint existed nothing could see the difference.
    grading_sigs: list[dict] = []
    for r in runs:
        sig = r.get("grading")
        if sig is not None and sig not in grading_sigs:
            grading_sigs.append(sig)

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
        "mixed_grading": len(grading_sigs) > 1,
        "grading": grading_sigs,
        # runs the cap actually bound — a truncated session with no reconcile is a different
        # data point, and unlike the configured cap it is worth flagging
        "capped_runs": capped,
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
            f"turn_cap={sig.get('turn_cap')} prompts={sig.get('prompts') or 'unstamped'} · {agents}")


def _fmt_grading(sig: dict) -> str:
    model, temp = sig.get("grader") or (None, None)
    return (f"rubric {sig.get('rubric')} @ {sig.get('sha256') or 'unstamped'} "
            f"· grader={model}@{temp}")


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
    if batch.get("mixed_grading"):
        L.append(f"  !! MIXED GRADING       : {len(batch['grading'])} distinct instruments "
                 f"scored this batch — the scores below are not comparable:")
        for i, sig in enumerate(batch["grading"], 1):
            L.append(f"       [{i}] {_fmt_grading(sig)}")
        L.append("     Re-grade the batch on one instrument (`bench grade --force`); the")
        L.append("     archives are untouched ground truth, so nothing is lost by re-scoring.")
    elif batch.get("grading"):
        L.append(f"  grading instrument     : {_fmt_grading(batch['grading'][0])}")
    if batch["capped_runs"]:
        L.append(f"  !! TURN-CAP TRUNCATED   : {len(batch['capped_runs'])} run(s) hit the cap "
                 f"without wrapping — no reconcile, no stage findings:")
        for rid in batch["capped_runs"]:
            L.append(f"       {rid}")
        L.append("     These are not comparable to runs that closed naturally. Raise the cap")
        L.append("     and re-run them, or read the batch without them.")
    if batch["unmanifested"]:
        L.append(f"  !! UNMANIFESTED ARCHIVES: {len(batch['unmanifested'])} — scored as if they "
                 f"never played:")
        for rel in batch["unmanifested"]:
            L.append(f"       {rel}")
        L.append("     Fold them into their run's archive or add them to batch.jsonl; until")
        L.append("     then every number below understates the violations.")
        L.append("     (A run still in flight looks like this too — its manifest line is")
        L.append("      written when it finishes.)")

    L.append("")
    L.append("── Score ───────────────────────────────────────────────────────────────────")
    if batch["score"]:
        s = batch["score"]
        L.append(f"  INTEGRITY SCORE        : {_fmt_dist(s, dp=1)}")
        if s.get("ci95") is not None:
            L.append(f"    95% CI on the mean   : {s['mean']:.1f} ± {s['ci95']:.1f} "
                     f"({s['mean'] - s['ci95']:.1f} – {s['mean'] + s['ci95']:.1f}, n={s['n']})")
            L.append(f"    resolution           : a second batch of {s['n']} would have to differ "
                     f"by ~{s['resolution95']:.0f} pts to be")
            L.append(f"                           distinguishable from this one. Smaller changes "
                     f"are invisible at this n.")
        L.append(f"  penalty rate (pts/unit): {_fmt_dist(batch['penalty_rate'], dp=2)}")
        L.append("  by dimension (score · violations across the batch):")
        thin = []
        for d in _DIMENSIONS:
            dist = batch["dimension_scores"].get(d)
            n = batch["dimension_violations"].get(d, 0)
            mark = " !" if n < _THIN_DIMENSION else "  "
            if n < _THIN_DIMENSION:
                thin.append(_DIM_LABEL[d])
            L.append(f"    {_DIM_LABEL[d]:<24} {_fmt_dist(dist, dp=1):<62} {n:>3} viol{mark}")
        L.append(f"  (weights {', '.join(f'{s}={p:g}' for s, p in _PENALTY.items())}; "
                 f"0 at {_FLOOR_RATE:g} pts/unit)")
        if thin:
            L.append(f"  ! under {_THIN_DIMENSION} violations batch-wide — that subscore is a "
                     f"handful of severity labels, and")
            L.append(f"    a label is only ~80% reproducible. Read these as a pointer to go read "
                     f"transcripts,")
            L.append(f"    never as a number to track: {', '.join(thin)}.")
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
