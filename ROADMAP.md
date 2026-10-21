# ROADMAP — what's left, in order

Each track lists its tasks in the order they should be done. What a task *is* lives in the track's
design doc; this file only orders the work and keeps the open questions. Delete a task when it
lands — git history is the record.

## luna — rebuild the product for GPT-6 Luna

Design: [`design/luna.md`](design/luna.md). Tasks 6–8 need model quota.

6. **Live shakedown.** Two or three Hollowfell sessions on Luna; fix only failures the runs show.
7. **Between-session and combat shakedown.** Reconcile and plan from those runs, a fresh campaign
   through setup, and the first real fight. Read the gates' before/after and cut the ones that
   don't earn their place.
8. **Release.** Version bump, changelog, `README.md` for the Luna product.

## benchmark — measure the product, tier by tier

Design: [`design/benchmark.md`](design/benchmark.md). B-numbers are stages in that doc.

3. **B7 — after-play checker.** `bench check`: one rolling Luna session per run over the pristine
   start canon, structured findings.
4. **B8 — grader rework.** Sol at `high`, one session per run, confirm or reject with file access,
   checker precision in the report.
6. **B3 — the `low` baseline.** After luna 6 and benchmark 1–4: a Luna pilot sizes the batch, then
   bank the distribution.
7. **B9 — `medium` and `high` tiers, and ablations.** Decide what each tier strips from what the
   baseline shows.
8. **B10 — benchmark proper.** Batches per condition and the methodology writeup.

## packaging

The portability rules are `dev/MAINTAINING.md` § Portability.

1. **Validate on native Windows.** Probe the `@opencode/cli` install, opencode command resolution,
   process-tree kill, paths with spaces and ANSI on a real Windows box. If opencode itself is the
   problem, pin a known-good version and document it.

## Open questions

- **Fold each `.state.md` into its entity file?** A `## Now (as of S<n>)` section would halve the
  file count and remove a pair to keep in sync, at the cost of state updates editing the canon file.
  Unsure; revisit if luna 6–7 show state drifting from its info file.
- **Is the score model's 0-point floor calibrated anywhere real?** `scoring.score_violations` maps a
  penalty rate onto 0–100 with a provisional floor. Until the `low` baseline is banked only deltas
  are readable; retune from that baseline, never from the MiMo pilot.
- **Should `dev/test_*.py` become pytest tests?** They are standalone scripts with a homegrown `tmp`
  helper, so `pytest dev/` reports collection errors that look like breakage and are not.
  Converting makes the test command conventional; against it, the scripts work.
