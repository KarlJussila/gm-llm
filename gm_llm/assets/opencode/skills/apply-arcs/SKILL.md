---
name: apply-arcs
description: The post-session arc pass for ONE arc — reconcile the arc named in your brief toward what was actually played (a real revision of the living design body, not a status bump). Loaded by the dm during the post-session apply; the orchestrator dispatches it once per arc, after the digest and the analyst assessment exist.
---

# apply-arcs — reconcile one arc toward what was played

This is where the campaign's stories absorb what happened at the table. The runner played a session;
the arc named in your brief must now be **reconciled toward what was actually played** — a real
revision of the arc's living *design body*, never just a status line. The orchestrator runs this
pass **once per arc**; your scope is the one arc your brief names. (New minor arcs, the threads
dashboard, and the cross-arc sweep are separate dispatches — not yours here.)

## Read first
Read `campaign/feedback/arc-design.md` if it exists — accumulated player guidance on how arcs should
feel. Treat it as binding over the defaults here.

## The arc model
The campaign runs **one major arc plus minor arcs**, with minors hooking into and building on the
major. Arcs are structured throughlines (committed answers + turning points); **threads** are the
lighter leads (a lead/hook that isn't yet a story) and live in the dashboard, not as files.

## The two principles that govern every edit

> **1. Played beats planned.** The arc is a living plan; the transcript is what happened. When they
> disagree, the design bends toward play — you revise the arc, not reality.

> **2. Canon hardens on exposure.** A fact the player has already *learned or seen* in play is
> locked — never retcon it. A fact the player has **not** yet been exposed to is malleable: change
> it freely, even a core detail, if it makes for a more engaging story. This is the latitude a good
> DM has between sessions. "Commit every answer" still holds — you never leave a load-bearing answer
> blank or "DM decides" — but you may **re-commit a better answer** to anything the player hasn't
> touched.

The familiar adjustments — recommit, redirect, accelerate/decelerate, deepen, merge/split, resolve —
are **lenses**, not a step to perform. A single arc usually needs several at once; apply whichever
fit as you work the steps below.

## Input
- The **session digest** `campaign/sessions/session-{N}.md` — especially *Plan vs. actual*,
  *Narrative*, *Threads*, *Secrets & awareness*, *Knowledge gained*.
- The **assessment** `campaign/assessment/session-{N}-assessment.md` — its recommendation for
  *this* arc, and its engagement reads.
- The **arc** `campaign/arcs/{slug}.md` + `{slug}.state.md`.
- The **PC knowledge ledger** `campaign/characters/{pc}.knowledge.md` — your source of truth for
  what the player *has been exposed to* (and therefore what is now locked).

## First — did the session touch this arc?

Read the arc's design + state. From the digest and the assessment, collect what play did to *this*
arc: which turning points landed; which committed answers play engaged or contradicted; new
load-bearing questions play raised; NPCs/factions whose role or held-answer shifted; what the PC
learned that touches this arc (→ now locked); where it sits on its curve; which engagement path the
player took; hooks fired to/from other arcs or threads. That's your edit list for the steps below.

**If the session didn't touch the arc at all** — no beat, answer, NPC, or hook of it engaged, and
nothing the PC learned bears on it — **change nothing and report "untouched".** Done. (Exception: on
the **major** arc, still reconsider level pacing — step 10 — even when the narrative was untouched;
advancement is paced on the calendar, not on this arc's beats.)

## The reconcile steps — work them in order

**1. Reconcile turning points.** Mark which landed (and in which session). Rewrite any beat play
altered to match what actually happened or what now makes sense ahead. Add beats for new turning
points play created; rework or cut ones play made impossible. Every turning point still commits its
answer, `[hidden]` + `Known to`. For *pending* beats the player hasn't reached, redesign freely for
a stronger arc.

**2. Reconcile the committed answers.** For each answer: if the player now *knows* it, it's locked —
keep it verbatim. If play *contradicted* it, recommit a revised answer consistent with what was
played. For each new load-bearing question play raised, commit an answer now. For answers the player
hasn't touched, improve them if it strengthens the arc. Never blank, never "DM decides."

**3. Reconcile key NPCs & factions.** Update the arc's line for each whose role, want, or held-answer
shifted in play — the arc's reference to them and the answer it says they hold — and add any the arc
now leans on as `[[slug]]` links.

**4. Reconcile premise, core conflict & stakes.** Revise toward the story play is actually telling.
If a stake resolved or a new one emerged, write it in. Don't preserve a framing out of inertia — if
play has put a sharper conflict within reach and the player isn't locked into the old one, take it.

**5. Reconcile the tension curve & position.** Update where the arc sits on build-up → climax →
resolution, and re-pace the remaining beats to how fast play is actually moving (accelerate, or
stretch it out).

**6. Reconcile engagement paths.** The legitimately-open part. Reset direct / indirect / avoidance /
alternative to the route the player actually took and the options that now lie ahead from the
current position.

**7. Reconcile hooks to other arcs and threads.** If this arc fired a hook into another arc — or a
thread fed it, or it spun off a thread — update **both** sides' cross-references and the dependency
note, so a minor arc building on the major stays wired to it. Flag any new cross-arc dependency play
created.

**8. Flip spoiler flags for what the PC learned.** For every `[hidden]` fact *in this arc* the PC
learned this session, flip it to `[revealed: S{N}]` and update `Known to`.

**9. Append the Adjustment log entry.** Add one line: **S{N}:** what changed in this arc's
structure/details and the play that prompted it — the provenance of the body's evolution.

**10. Reconcile level pacing (the major arc only).** The major arc's *Level pacing* section is the
campaign's advancement schedule. Reconsider it **every pass, even if the arc was otherwise untouched**:
mark any level-up delivered this session (the digest / updated sheet shows it), then re-project the
schedule ahead — **drop, add, or move** milestones so the cadence still fits the PC's current level and
where the arc now sits (every 2–5 sessions, tighter at low levels / looser at high). Never let the
schedule stall or bunch two level-ups to catch up. A minor arc has no pacing section — skip this step.

**11. Update the arc's state file.** Rewrite `arcs/{slug}.state.md`: Status, Turning points hit
(+ session), Position on the tension curve, `as-of: S{N}`. The state is the quick at-a-glance read;
the body holds the substance.

## Report
Brief: **Result** (what changed in this arc — or "untouched"), **Caveats** (anything the
digest/assessment left ambiguous). The gate (`check-propagation`) audits the whole apply separately.

## Boundaries
- Your scope is **this one arc's design body and state file**. Creating new minor arcs, the threads
  dashboard, and the cross-arc sweep are separate dispatches; entity files, the PC knowledge ledger,
  and the global `state/*` snapshots are reconciled separately.
