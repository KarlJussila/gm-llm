# Handoff — the Luna prompt rework (2026-10-21)

Temporary: delete this file once ROADMAP luna 5 lands. The plan is `ROADMAP.md`; the design is
`design/luna.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`).

## Where things stand

- **luna 4** landed: Sol's pass (`32d01cd`), then a cleanup (`a488787`). Setup moves on after one
  arcs/state nudge, as reconcile does; agents read `feedback-dir` from `gm-llm.yaml` as written,
  because opencode's file tools expand `~` and relative paths themselves.
- **luna 5's sweep** landed (`74fb69b`): the in-play check skills and `design/runner-authority.md`
  are gone; README, `design/README.md` and `combat.md` describe the Luna product.
- Karl confirmed `as-of: S0` for setup. Old v0.5 campaigns on `~/Desktop` need no migration.
- **Tag `luna-clean-slate` only when the prompt rework is complete** and the product is ready to
  test (Karl, 2026-10-21) — the last step of ROADMAP luna 5, before the luna 6 shakedown.

## The prompt rework in progress

Rewriting every model-facing prompt still in MiMo form to `design/luna.md` § Principles and
`CLAUDE.md` § The prompts, via the `refine-prompts` method. No tag yet, so nothing is protected.
One commit per file or pair; Karl hasn't reviewed these yet — the skill's "approve the first few"
step was skipped because he was away, so he should look at the first commits' diffs.

Order (hot path first). Done is marked ✓.

- ✓ `social-play`, `discoveries` (`e961feb`)
- ✓ `combat-run` (now says to roll initiative), `combat-balance` (`035459f`)
- ✓ planning: the four `*-plan` skills, `check-plan`, its brief and correction, `setup-gate-brief`,
  `correct-init` (`c5e8073`)
- ✓ setup skills (`38768b3`); `dm.md`, `check-digest`, every skill description now "Load when …"
  (`6d3cd2f`); the orchestrator's nudges and combat briefs moved out of Python into `prompts/`, and
  `resume-prime` (`e2a20f1`)
- ✓ B6, the autoplayer (`54f1203`, recap in the next commit): `player.md`, the `player-rolls` / `player-combat` skills
  (scoped to the player agent by `skill` permissions, verified with `opencode debug agents` in a
  scratch project), and the packet generated in code (`orchestrator/packet.py`). Only the
  story-so-far recap (`dev/fixtures/hollowfell/story.md`) was written from the two transcripts by
  Claude, not Luna — Karl to review it by hand.

Find what's left with `git log --format=%h 1f6879a..HEAD -- <file>`: a file touched only by
`1974a4b` (the mechanical layout change) or not at all is still MiMo prose.

## Open, outside the repo

- Karl's global `~/.config/opencode/plugin/task-signal.ts` and `plugins/dice-roller.ts` are v1
  plugins and fail to load under opencode 2.x.
- Native Windows is untested (ROADMAP packaging 1).
