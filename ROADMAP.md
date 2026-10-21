# ROADMAP — what's left, in order

Each track lists its tasks in the order they should be done. What a task *is* lives in the track's
design doc; this file only orders the work and keeps the open questions. Delete a task when it
lands — git history is the record.

## luna — rebuild the product for GPT-6 Luna

Design: [`design/luna.md`](design/luna.md). Tasks 3–5 need no model quota; 6–8 do.

3. **Reconcile and planning.** Whole-transcript digest; the assessment, `campaign-analyst` and
   `check-feedback` deleted; feedback curation on the `dm` thread; arcs through Luna-pinned
   subagents with code-verified coverage; `check-propagation` reduced to its judgment half;
   before/after archived for every gate; `session-plan` without choreography.
4. **Setup and player-level feedback.** A world proposal the player can revise before character
   creation; one arcs-and-state dispatch with code checks; `check-init` reduced to its judgment half;
   `campaign-setup` deleted; the player-level feedback store and the `subagents` setting.
5. **Sweep out what MiMo left.** Delete the agents, skills, briefs and tests nothing calls any more,
   and `design/runner-authority.md`; bring `README.md` and `design/README.md`'s architecture in line
   with the rebuilt product. Then tag the commit `luna-clean-slate` — the baseline the
   `refine-prompts` skill protects everything after.
6. **Live shakedown.** Two or three Hollowfell sessions on Luna; fix only failures the runs show.
7. **Between-session and combat shakedown.** Reconcile and plan from those runs, a fresh campaign
   through setup, and the first real fight. Read the gates' before/after and cut the ones that
   don't earn their place.
8. **Release.** Version bump, changelog, `README.md` for the Luna product.

## benchmark — measure the product, tier by tier

Design: [`design/benchmark.md`](design/benchmark.md). B-numbers are stages in that doc.

1. **B5 — conditions and tiers.** The tier as a real field, reasoning variants, subagents in the
   conditions, `--subject-model`, feedback isolation.
2. **B6 — autoplayer on Luna.** `player.md` and its two skills, the packet generated in code. The
   story-so-far recap needs quota.
3. **B7 — after-play checker.** `bench check`: one rolling Luna session per run over the pristine
   start canon, structured findings.
4. **B8 — grader rework.** Sol at `high`, one session per run, confirm or reject with file access,
   checker precision in the report.
5. **`bench status`.** Batch state by outcome without a throwaway script.
6. **B3 — the `low` baseline.** After luna 6 and benchmark 1–4: a Luna pilot sizes the batch, then
   bank the distribution.
7. **B9 — `medium` and `high` tiers, and ablations.** Decide what each tier strips from what the
   baseline shows.
8. **B10 — benchmark proper.** Batches per condition and the methodology writeup.

## frontends

Design: [`design/frontends.md`](design/frontends.md).

1. **Route console autoplay through `Lifecycle`.** The last direct `Game` construction — duplication
   to retire, not a gap. Needs `player_source()` to carry the resume story.

## packaging

The portability rules are `dev/MAINTAINING.md` § Portability.

1. **Validate on native Windows.** Probe opencode command resolution, process-tree kill, paths with
   spaces and ANSI on a real Windows box. If opencode itself is the problem, pin a known-good version
   and document it.

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
