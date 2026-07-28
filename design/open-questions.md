# Open questions / loose ends

The live backlog of **unresolved** decisions and known gaps. When one is resolved, the
resolution is recorded in that round's Part in `findings.md` and the item is **deleted from
here** — no "RESOLVED" tombstones.

**Park work on a track, never on a round.** A round closes; a track persists. An item that
says "fix this during the X round" becomes a dangling pointer the moment that round lands.
Name a ROADMAP track, or better, a *condition* ("when a second frontend needs it").
`tools/lint_docs.py` check 6 warns on round-shaped phrasing with no track.

## Needs Karl

### The live-model shakedown has never happened

Carried over from the prior plan and still owed: a real new-campaign run (setup + a character
import) plus a post-session pass against the live model, exercising the per-arc apply briefs
and the slimmed checker skills. Combat (`COMBAT.md`) is in the same position — C0–C5, AoE and
resume-hardening are all mock-verified only. Neither is blocking, but every round that lands
orchestrator changes widens the gap between what the tests prove and what has ever run.
Parked on ROADMAP track **live**.

### Model configuration is deferred by agreement

`PLAN.md` § 2 leaves model configuration out of the packaging work. Unblocking it needs a
decision on whether the campaign or the install owns the choice. Parked on ROADMAP track
**packaging**.

## Benchmark

### Is the score model's 0-point floor calibrated anywhere real?

`scoring.score_violations` maps a penalty *rate* to 0–100 with 0 at 2 points/unit. BENCHMARK.md
says outright this is a display calibration to retune once B3 shows where tier 0 lands. Until
the baseline is banked the absolute score means nothing and only deltas are readable — which
is worth stating wherever a score is reported. Parked on ROADMAP track **benchmark** (B3).

### The player-end contract is still loose

BENCHMARK B1 names this a prereq to finalizing the bench: **where** the play packet lives
(root vs `campaign/documents/` — `character_packet` is a stopgap), **how** it is generated
(hand-merged from the player-known layer today), and **how** it is loaded (`fixture.json` for
bench, `--character` for autoplay). One canonical home, one generation path, one load contract.
Parked on ROADMAP track **benchmark**.

## Frontends

### What does cancel mean for an unattended run?

`ctrl+x` cancels a turn in the TUI. If a bench batch renders in the TUI, cancel has no obvious
semantics — abandon the turn, the run, or the batch? Needs deciding before batch chrome lands,
not after. Parked on ROADMAP track **frontends** (step 4).

### Should `ui` be a recorded condition?

`design/frontends.md` argues no: stamping it fragments the baseline, and the honest invariant
is that the frontend never touches the archive path. But that invariant currently has nothing
enforcing it. If it stays unenforced, the argument for not stamping gets weaker. Parked on
ROADMAP track **frontends**.

## Docs / infra

### Should `dev/test_*.py` become real pytest tests?

They are standalone scripts with a homegrown `tmp` helper, so `pytest dev/` yields ~47
collection errors that look like breakage and are not (Part 1). Converting would make the gate
conventional and give a cold session what it will reach for anyway. Against: the gate works,
and changing it is not free. Parked on ROADMAP track **docs**.

## Watch-list (no action unless it recurs)

- **Prompt corpus size as a proxy.** `status.py` reports lines of model-facing prose by
  bucket. It is not yet clear that the number is *load-bearing* rather than decorative — if
  two rounds pass without anyone acting on it, delete it per the numbers rule.
