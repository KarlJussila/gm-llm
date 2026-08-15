# ROADMAP — all planned work, sequenced

The single sequence for everything that remains, with a **recommended effort level per task**.
What each task *is* lives in the linked plan-of-record docs — this file orders the work and says
how hard to think about it. Pickup and handoff live in `CLAUDE.md` § Standing rules; the active row
is `HANDOFF.md` § Next task.

## Effort levels

| Effort | Use for | Discipline |
|---|---|---|
| **low** | Checklist work, fully specified, with the gate catching errors | Trust the gate; don't redesign in passing |
| **medium** | Specified implementation that still encodes a contract | The default |
| **high** | Decisions, contract reviews, first-of-kind work with no oracle | Spend it on choices that are expensive to reverse, never on labor |

**Model-facing work is never low.** The gate proves the harness works, not that a DM improved.
Tier-0 prose is frozen; Luna prose is validated from live evidence and then profile-stamped runs.

## luna — build Tier 1 for Luna from first principles

Plan of record: [`design/luna.md`](design/luna.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Run the clean Luna live-play probe | high | Use Hollowfell with `opencode/gpt-5.6-luna` at `xhigh`: minimal role/contract, deterministic tools, raw capture; no Tier-0 reminders, todo choreography, forced skills, or correction delivery. The output is the smallest evidence-backed live-play contract, not production tier plumbing |
| 2 | Build the concrete Tier-1 live-play vertical slice | high | Dedicated Luna assets plus public profile selection through the existing play UI; add only seams the probe proves, keep the MiMo checker observe-only, and hold Tier 0 byte-stable under the golden stream |
| 3 | Re-author setup and reconcile around Luna | high | Preserve their public outcomes, not Tier 0's two-agent split or micro-stage graph. Start with the largest coherent tasks and split only where a Luna run shows quality or recovery needs it |
| 4 | Close Tier-1 operational gaps | medium | Resume, cancellation, context pressure, combat, checkpoints, update, and campaign selection/migration work end to end; includes the real combat shakedown the current product never received |
| 5 | Shakedown, promote, and release Tier 1 | high | Run a real new campaign through setup → play → reconcile, bank acceptance evidence, make Luna the recommended new-campaign profile, and keep MiMo Tier 0 selectable |

## benchmark — measure concrete profiles

Plan of record: [`design/benchmark.md`](design/benchmark.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | B1 prereq — pin the player-end contract | high | One home, one generation path, one load contract for the play packet; needed for unattended multi-session runs regardless of profile |
| 2 | `bench status` — batch state without a throwaway script | low | Runs by outcome are still hand-derived; include per-turn `tools`/`stale` for historical Tier-0 reads without making them Tier-1 requirements |
| 3 | B5/B6 — profile identity and observe-only instrumentation | medium | After Luna 2 establishes the real profile seam, stamp profile + reasoning and run the common instrument without feeding MiMo correction prose into Luna |
| 4 | B3/B7 — bank the Luna baseline | medium | After Luna 5 is viable, size from a Luna pilot and bank an identical-condition Tier-1 distribution; the MiMo pilot supplies methodology, not the sample size or a prerequisite |
| 5 | Focused ablations and benchmark writeup | high | Test only observed mechanisms, then make causal claims from controlled conditions rather than treating two whole products as a single difficulty ladder |

## frontends — mode × frontend modularity

Plan of record: [`design/frontends.md`](design/frontends.md).

| # | Task | Effort | Why |
|---|---|---|---|
| 5 | Route console autoplay through `Lifecycle` | low | The last direct `Game` construction. Blocks nothing — duplication to retire, not a gap; needs `player_source()` to carry the resume story |

## packaging — native Windows

The portability rules are `dev/MAINTAINING.md` § Portability. Profile ownership resolves the old
model-configuration question: the install ships definitions, and a campaign selects one.

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Validate on native Windows | medium | Probe opencode command resolution, process-tree kill, paths with spaces, and ANSI on a real Windows box. If opencode itself is the problem, pin a known-good version and document it |

## docs — keep the loop honest

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Generate `findings.md` § Contents | low | Hand-maintained indexes have drifted repeatedly; automate the index before the archive grows further |
| 2 | Decide on pytest for `dev/test_*.py` | medium | Changes the gate, so it remains its own coherent task (`design/open-questions.md`) |
| 3 | `sessions/` → per-session directories | high | A cross-cutting path refactor with no behavior change to show for it; keep it separate (`design/open-questions.md`) |

## Landed

| Track | Parts | Outcome |
|---|---|---|
| docs | 1 | The handoff-round loop stood up: five docs, `status.py`, `lint_docs.py`, `close-round`; `dev/MAINTAINING.md` reconciled |
| docs | 2 | Planning consolidated onto the loop: old duplicate plans deleted, plan-of-record docs routed through `design/`, lint checks added |
| packaging | 2 | Native-Windows portability changes built; real-box validation remains |
| frontends | 3–6 | Combat and session loops unified; bench routed through `Lifecycle`; unattended runs became watchable without perturbation |
| benchmark | 7 | The MiMo pilot exposed large variance, instrument identity gaps, and runner failures; its methodology survives while its scores describe a superseded subject |
| recalibration | 8–9 | MiMo runner authority audited; one reminder/staleness experiment landed. Remaining recalibration retired when Tier 0 froze |
| direction | 10 | MiMo frozen as playable Tier 0; Luna at `xhigh` selected for a clean Tier-1 path; generic tier/playbook extraction removed as a prerequisite |

## Standing sync rules

- **Tier 0 is frozen, not deleted.** Its prompts and orchestration change only for a supported-path
  regression or provider drift. Shared-substrate work keeps its golden prompt stream clean.
- **A concrete Luna path comes before generic profile machinery.** Luna 1 is diagnostic and Luna 2
  adds only its proven seams. Extract a shared abstraction only after both product paths need it.
- **The Tier-0 pilot does not gate Tier 1.** It remains evidence about methodology and MiMo. Luna's
  own pilot sizes Luna's baseline after the product path is viable.
- **The checker is observe-only for Tier 1 by default.** Every run remains measurable, but a MiMo
  instrument does not steer Luna unless a focused experiment demonstrates a gain.
- **Model and reasoning are condition identity.** Tier 1 begins at Luna `xhigh`; a different effort
  is a different benchmark condition, not a casual config edit.
