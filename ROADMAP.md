# ROADMAP — all planned work, sequenced

The single sequence for everything that remains, with a **recommended effort level per task**.
What each task *is* lives in the linked plan-of-record docs — this file only orders the work
and says how hard to think about it.

How a session picks up and hands off: `CLAUDE.md` § Standing rules. The live "task now"
pointer is `HANDOFF.md` § Next task.

## Effort levels

| Effort | Use for | Discipline |
|---|---|---|
| **low** | Checklist work, fully specified, with the gate catching errors | Trust the gate; don't redesign in passing |
| **medium** | Specified implementation that still encodes a contract | The default |
| **high** | Decisions, contract reviews, first-of-kind work with no oracle | Spend it on choices that are expensive to reverse, never on labor |

**Prompt-prose work is never low.** The gate proves the harness works; it says nothing about
whether a prompt change made the DM better, and no score baseline is banked yet (track
**benchmark**, B3). Until one is, every change under `gm_llm/assets/opencode/` or
`gm_llm/orchestrator/prompts/` is at least medium and leans on the git-archaeology discipline
in `CLAUDE.md` § Writing prompts.

Fan-out to workers is a *method*, not a level: rows that name it mean the round batches menial
items out and the **driving session re-verifies every result**.

## frontends — mode × frontend modularity

Plan of record: [`design/frontends.md`](design/frontends.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Unify the two `_play_combat` implementations | medium | `autoplay.py:41` and `runner.py:279` are near-duplicates that differ in turn accounting; bench's PC-slot-counts-as-a-turn semantics are load-bearing for the cap and must survive |
| 2 | `PlayerSource` — one turn loop, keyboard or agent | high | The fork between pull-driven TUI and push-driven autoplay is the actual blocker; first-of-kind, no oracle |
| 3 | Route bench through `Lifecycle` | medium | Bench constructs `Game` directly and reaches the reconciler via `reconcile_fn`, bypassing the interface the TUI is written against |
| 4 | Batch chrome in the TUI (run *k* of *N*) | medium | `PlayApp` assumes one campaign dir for the app's life; needs the cancel-semantics decision first (`design/open-questions.md`) |

## benchmark — the instrument

Plan of record: [`BENCHMARK.md`](BENCHMARK.md) (B-numbers are its sections).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | B1 prereq — pin the player-end contract | high | One home, one generation path, one load contract for the play packet; BENCHMARK calls it a prereq to finalizing the bench |
| 2 | B3 — bank the baseline batch | medium | 5–10 identical-condition tier-0 runs on untouched prompts. Everything after it is anchored to it; **nothing model-facing changes until it lands** |
| 3 | `bench status` — batch state without a throwaway script | low | Runs by outcome (complete / capped / reconcile-pending) is a number this repo keeps hand-deriving; `bench-out/` is gitignored so it can't live in `status.py` (Part 1) |
| 4 | B4 — golden prompt-stream test | medium | Free regression armor; B5 must diff clean against it |
| 5 | B5 — playbook extraction | high | Extract the invariant engine; verified twice (golden diff mandatory, confirmation batch optional) |
| 6 | B6–B9 — tier plumbing, then tier authoring | high | Not startable until B5; B7 (bare) is authored before B8 (standard) because the extreme tier stress-tests the contract fragments |

## live — shakedown against a real model

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | New-campaign shakedown (setup + character import) | medium | Owed since the prior plan; exercises the per-arc apply briefs and slimmed checker skills |
| 2 | Combat shakedown | medium | C0–C5, AoE and resume-hardening are all mock-verified only ([`COMBAT.md`](COMBAT.md)) |

## packaging — native Windows and easy setup

Plan of record: [`PLAN.md`](PLAN.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Phase 1 — native Windows portability | medium | In progress per PLAN.md § 2 |
| 2 | Phase 3 — validate on native Windows | medium | The biggest external unknown; needs a real Windows box |
| 3 | Model configuration | high | Deferred by agreement; needs the campaign-vs-install ownership decision (`design/open-questions.md`) |

## docs — keep the loop honest

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Generate `findings.md` § Contents | low | Hand-maintained indexes fall behind the archive they index; do it before the archive is long enough to matter |
| 2 | Decide on pytest for `dev/test_*.py` | medium | Changes the gate, so it is its own round (`design/open-questions.md`) |

## Landed

| Track | Parts | Outcome |
|---|---|---|
| docs | 1 | The handoff-round loop stood up: five docs, `status.py`, `lint_docs.py`, `close-round`; `dev/MAINTAINING.md` reconciled |

## Standing sync rules

- **Nothing model-facing changes before B3 banks the baseline.** That is BENCHMARK's own
  rule and it constrains every other track: prompt edits, tier work, and any refactor that
  could move the prompts wait behind it. Harness-only work (frontends, packaging, docs) runs
  alongside freely.
- **frontends 1–3 land before 4.** Batch chrome renders a driver that must already be unified;
  building the chrome first means building it twice.
- **B4 lands before B5.** The golden stream is the only thing that makes the playbook
  extraction verifiable as behavior-preserving.
- **The live shakedowns can run at any time** and should run before, not after, a release that
  touches the orchestrator.
