---
name: refine-prompts
description: Use when asked to trim, refine, prune or tighten gm-llm's model-facing prompts — an agent, a SKILL.md or an orchestrator brief under gm_llm/assets/opencode or gm_llm/orchestrator/prompts — or to cut prompt verbosity without losing guardrails added since the clean slate.
---

# refine-prompts — prune prompt bloat, keep the scar tissue

Prompts accrete: a line added to fix an observed model failure looks like bloat a few months later,
and naive trimming deletes the guardrail. This skill is the disciplined pass. The writing rules are
`CLAUDE.md` § The prompts; this is the process for applying them to existing prose.

## The clean slate

The Luna rebuild (`ROADMAP.md` track luna, tasks 1–5) rewrites every prompt from first principles.
When it lands, the commit is tagged **`luna-clean-slate`**. That tag splits the prose in two:

- **Written before the tag** — the rebuild's baseline. Not sacred: cut or rewrite it on the writing
  rules alone.
- **Written after the tag** — scar tissue until proven otherwise. A line added after the clean slate
  was almost always added because a Luna run failed without it. Cut it only after the archaeology
  below shows the constraint is redundant, stated elsewhere, or no longer reachable.

If the tag doesn't exist yet, the rebuild is still writing the baseline and nothing is protected.

## Scope and order

1. Inventory with `wc -l`: agents (`gm_llm/assets/opencode/agent/*.md`), skills
   (`.../skills/*/SKILL.md`), orchestrator briefs (`gm_llm/orchestrator/prompts/*.md`).
2. Go **hot path first** — the prose read every session, so gains compound: `dm-runner`, then the
   play skills it loads (`social-play`, `discoveries`, `session-close`, `combat-run`), then planning,
   setup and reconcile.

## Per file, section by section

1. **Find what's protected.** `git blame luna-clean-slate.. -- <file>` marks every line from before
   the tag with a leading `^`; the unmarked lines are post-baseline.
2. **Archaeology on the unmarked lines.** `git log --oneline luna-clean-slate.. -- <file>`, then
   `git show <sha>` where a block's intent is unclear. The commit message should name the failure the
   line repairs and the run that showed it.
3. **Classify each block:**
   - **Cut** — redundancy (one rule stated two or three ways), hedging, meta-commentary, filler.
   - **Compress** — keep the constraint and any concrete failure cue or example; tighten the prose
     around it.
   - **Keep verbatim** — post-baseline scar tissue whose exact wording is what fixed the failure.
4. **Apply the writing rules** (`CLAUDE.md` § The prompts and `design/luna.md` § Principles): one
   home per rule; every-turn rules in the agent prompt, situational craft in skills; a skill's
   description says when to load it; no instructed choreography.
5. **Fix, don't preserve, errors.** Check the rules in every example; a wrong example teaches the
   wrong rule.
6. When cutting a post-baseline line that looks load-bearing, **cite the commit** that keeps its
   constraint alive elsewhere, so the reviewer sees the intent survives.

## Adding a guardrail

The archaeology only works if the history is written for it. A commit that adds a guardrail after
the clean slate names the failure it repairs and where it was seen (a shakedown session, a bench
run id). "Tighten session-close" is useless to the next pass; "session-close: Luna asked for
feedback before landing the ending (bench run 20261102T…)" is what lets someone decide later.

## Review cadence

Calibrate, then loosen: for the first few files, show the diff and the git rationale and get
approval before committing. Once the judgment is calibrated, review batches by combined diff. One
commit per file or per logical change, saying what collapsed and that no constraint was dropped.

## Guardrails

- **Measure when you can.** Until the `low` baseline is banked (`design/benchmark.md` B3), prose
  changes aren't measured, so archaeology is the only safety net — bias toward keeping a
  post-baseline constraint. Once the baseline exists, a non-trivial trim of hot-path prose gets a
  bench batch before it's trusted.
- **Propagation:** changes reach a live campaign via `pipx reinstall` + `gm-llm update`; never while
  a TUI session is running.
