---
name: close-round
description: Close a round of work in gm-llm — run the full gate, append the findings Part, regenerate HANDOFF's numbers, prune ROADMAP, and hand off to the next session. Use at the end of every work round, when asked to "close the round", "update the docs and hand off", "wrap up and commit", or after finishing the task HANDOFF.md named. Also use when a session is about to run out of context and needs to hand off mid-task.
---

# Close a round

One session = one ROADMAP task. A round that lands work but doesn't close the docs and commit
**has not been handed off** — the next session starts cold and re-derives what you knew, badly. This is
the procedure. Work top to bottom.

## 1 — Pass the gate

Every command, every round. Not "it should be fine".

```sh
python -m compileall gm_llm
for t in dev/test_*.py; do echo "== $t"; python "$t" || break; done
python3 tools/status.py --check
python3 tools/lint_docs.py
```

**Do not run the suite under pytest.** `dev/test_*.py` are standalone scripts with their own
`tmp` helper; `pytest dev/` yields a wall of `fixture 'tmp' not found` collection errors that
are convention mismatch, not failures (Part 1).

**A red suite is this round's problem even if this round didn't break it.**

If the round touched `gm_llm/assets/opencode/` or `gm_llm/orchestrator/prompts/`: there is no
score baseline yet (BENCHMARK B3), so the gate cannot tell you whether the prose got better.
Lean on the git-archaeology discipline in `CLAUDE.md` § Writing prompts and say in your Part
what you could not verify.

## 2 — Regenerate, don't transcribe

```sh
python3 tools/status.py --write     # rewrites HANDOFF's numbers block
python3 tools/lint_docs.py          # 0 errors AND 0 warnings
```

> **The numbers rule.** A count lives in a ratchet a tool enforces, in the generated block, or
> **nowhere**. Never type one into prose. If you catch yourself writing "2,677 lines of
> skills", stop and delete it. HANDOFF is *rewritten* every round, and a session rewriting a
> doc reconstructs numbers from context instead of re-running the command — which is exactly
> how they drift.

**Warnings count.** A `lint_docs.py` warning is the repo telling you that you are re-creating
a debt class it already paid to clean up. Clear every warning, or name each survivor in your
Part and say why it stays.

**Re-read every doc edit you make.** Scripted edits to markdown fail silently: a `str.replace`
whose pattern doesn't match changes nothing and reports nothing. If you edit a doc with a
script, `grep` the result back.

## 3 — Append the findings Part

Append to `design/findings.md`, in the house heading form so the index stays generatable:

```
# Part N — Subject: what it's about (YYYY-MM-DD)
```

Sections: **The gap** (what was wrong before), **What the round does** (the change, plus the
reasoning behind any non-obvious call), **Declared lossiness / deferrals** (what you knowingly
left undone, so a later audit can find it), **Green bar** (that the gate passed).

Write it so someone hitting the same problem class in forty rounds finds the precedent. Add
the row to § Contents. If the round established a pattern worth naming, add it to § Recurring
threads.

**Old Parts are never retro-edited.** They are point-in-time on purpose — that is the whole
value of an archive. Let them go stale.

## 4 — Rewrite HANDOFF.md

**Rewrite, don't patch.** Fresh "where things stand", and a **new § Next task** naming the next
ROADMAP row and its effort level, with any precondition and the known traps. Rewriting is what
keeps it from silting up; the lint enforces the line budget.

If you are handing off mid-task because you are out of context, say so explicitly in § Next
task — what is done, what is not, and what the next session should read first.

## 5 — Update ROADMAP and the backlog

- A shipped row is **deleted** from its track table and replaced by one line in § Landed
  pointing at the Part. Do not leave it in place with a ✅ and a completion narrative — that
  is how a roadmap turns into a second, staler copy of the archive. (`lint_docs.py` check 9.)
- Sequencing changed? Update the track tables and § Standing sync rules.
- Add anything unresolved to `design/open-questions.md`; **delete** anything this round
  resolved (the resolution lives in your Part).
- Park deferrals on a **track**, never on a round. Prefer a condition ("when a second frontend
  needs it") over a schedule.
- Update whatever plan-of-record doc the round actually changed.

## 6 — Commit

**Closing a round commits it. Don't ask.** An uncommitted round is not closed — the docs say
work landed and the tree says otherwise, and the next session inherits the discrepancy (Part 3
found exactly that). This is gm-llm's carve-out from the standing "commit only when asked" rule,
and it is the only one: `CLAUDE.md` § Standing rules states it.

Messages are short, plain, descriptive, with **no attribution trailer**. One round, one commit,
subject naming what landed. If the round is worth a `CHANGELOG.md` line, add it under
`[Unreleased]` — and if it completes a feature set, say so, because that is a version bump
heading toward you (`CLAUDE.md` § Versioning & releases).

**If something needs Karl's attention, raise it *instead of* closing — not after.** A round that
ends with "here are the results, and also a question you have to answer" has handed him a choice
he can no longer make cleanly, because the docs and the commit already assume an answer. Stop at
the point of doubt, say what you found and what it forks on, and close the round once it's
settled. Things that fork a round: a design call the plan of record doesn't cover, a gate failure
whose right fix is arguable, work that turns out to belong to a different track, or a tree that
isn't what HANDOFF says it is.

**Before you stage, check what else is in the tree.** `git status --porcelain` — if it carries a
previous round's work (HANDOFF claiming "clean" is not evidence; check), do **not** sweep it into
this round's commit. Reconstruct the earlier state by reverse-applying this round's hunks, verify
*that* tree against the gate, commit it under its own message, then restore this round's work on
top. Snapshot your final files first; a bad reverse-apply is otherwise unrecoverable. (Part 3.)

## When a cleanup round is needed

**A cleanup round is a signal, not a chore.** If the docs need one, the loop is missing a
check — so spend the round building the check in `tools/lint_docs.py`, not just fixing the
symptoms. Fixing symptoms alone schedules the same round again later.
