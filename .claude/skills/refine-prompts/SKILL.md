---
name: refine-prompts
description: Trim bloat from gm-llm's model-facing prompts (agents, skills, orchestrator briefs) without losing hard-won guardrails, using git archaeology to justify every cut. Use when asked to trim, refine, prune, or tighten prompts — a SKILL.md, an agent, or a turn brief — or to reduce prompt verbosity anywhere under gm_llm/assets/opencode or gm_llm/orchestrator/prompts.
---

# refine-prompts — prune prompt bloat, keep the scar tissue

gm-llm's prompts accrete: most lines were added to fix a specific model failure, so naive trimming
deletes guardrails. This is the disciplined pass. The *conventions* live in `CLAUDE.md` ("Writing
prompts"); this skill is the *process* for applying them to existing prose.

## Scope and order

1. Inventory with `wc -l`: agents (`gm_llm/assets/opencode/agent/*.md`), skills
   (`.../skills/*/SKILL.md`), orchestrator briefs (`gm_llm/orchestrator/prompts/*.md`).
2. Go **runtime hot-path first** — read every turn, so gains compound: dm-runner, session-run,
   social-play, session-flow, discoveries, narrative-checker, check-turn → then planning, setup,
   reconcile.

## Per file, section by section

1. **Archaeology.** `git log --oneline --follow -- <file>`, then read the commit subjects (and
   `git show <sha>` where a block's intent is unclear) to learn *why* each block exists. The commit
   messages narrate the failure each rule encodes.
2. **Classify each block:**
   - **Cut** — redundancy (one rule stated two or three ways), hedging, meta-commentary, filler intros.
   - **Compress** — keep the constraint and any concrete failure-mode cue/example; tighten the prose
     around it.
   - **Keep verbatim** — scar tissue where the wording itself is load-bearing.
3. **Apply the modularization rules** (CLAUDE.md): canonical home + point-don't-restate; the
   universal-vs-scene-specific scope test before moving a rule into a companion skill; explicit
   "load X and follow it" handoffs; don't re-enumerate a loaded skill's steps.
4. **Fix, don't preserve, errors** — verify rules correctness in examples; a wrong example teaches the
   wrong thing.
5. When cutting a line that looks load-bearing, **cite the commit** that keeps the underlying
   constraint alive, so the reviewer sees intent is preserved, not lost.

## Review cadence

Calibrate then loosen: for the first few files, show the diff + git rationale and get approval before
committing; once judgment is calibrated, move to batches reviewed by combined diff. One commit per
file (or per logical change), with a message that says what was collapsed and that no constraints were
dropped.

## Guardrails

- **No score baseline is banked yet** (`design/benchmark.md` B3): prose changes aren't measured, so git
  archaeology is the only safety net — bias toward preserving every constraint.
- **Trim in place; never recompose or template tier-0 prose.**
- **Propagation:** committed changes reach a live campaign via `pipx reinstall` + `gm-llm update`;
  never do it while a TUI session is running.
