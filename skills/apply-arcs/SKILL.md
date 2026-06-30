---
name: apply-arcs
description: The post-session arc pass — reconcile each arc the session touched toward what was actually played (a real revision of the living design body, not a status bump), create any new minor arc play has birthed (via arc-design), and update the threads dashboard. Loaded by the dm during the post-session apply. Per-arc; runs after the digest and the analyst assessment exist.
---

# apply-arcs — the post-session arc pass

This is where the campaign's stories absorb what happened at the table. The runner played a session;
each arc it touched must now be **reconciled toward what was actually played** — a real revision of
the arc's living *design body*, never just a status line. This is the core of keeping the campaign
coherent and alive over many sessions.

## Read first
Read `campaign/feedback/arc-design.md` if it exists — accumulated player guidance on how arcs should
feel. Treat it as binding over the defaults here.

## The arc model
The campaign runs **one major arc plus minor arcs**, with minors hooking into and building on the
major. Arcs are structured throughlines (committed answers + turning points); **threads** are the
lighter leads (a lead/hook that isn't yet a story) and live in the dashboard, not as files. A thread
that grows committed answers and turning points is **promoted to a minor arc**.

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
fit as you work the edits below.

## Input
- The **session digest** `campaign/sessions/session-{N}.md` — especially *Plan vs. actual*,
  *Narrative*, *Threads*, *Secrets & awareness*, *Knowledge gained*.
- The **assessment** `campaign/assessment/session-{N}-assessment.md` — read it for its arc
  recommendations and engagement reads.
- The **arcs** `campaign/arcs/{slug}.md` + `{slug}.state.md`, `campaign/INDEX.md` (Arcs), and the
  **threads** dashboard `campaign/state/threads.md`.
- The **PC knowledge ledger** `campaign/characters/{pc}.knowledge.md` — your source of truth for
  what the player *has been exposed to* (and therefore what is now locked).

## Step 1 — Build your task list (one list, expanded one arc at a time)

You keep **one** todo list for the whole pass. `todowrite` **replaces the list wholesale** on every
call — there is no "add one item" or second list — so *every* call must pass the **entire** list:
the items already `completed`, the work in front of you, and everything still ahead. Dropping the
done items or the arcs still to come deletes them.

Start with these entries:

1. Identify affected arcs and threads
2. Reconcile the affected arcs   *(placeholder — you expand this once you know which arcs)*
3. Create any new minor arcs play has birthed (via `arc-design`)
4. Update the threads dashboard
5. Cross-arc / thread consistency sweep
6. Report

### 1. Identify affected arcs and threads
From *Plan vs. actual*, *Narrative*, and the assessment's recommendations, list every arc the
session **advanced, diverged from, or implicated** (at least one — every session moves an arc), and
every thread it touched or spawned. Note any thread that has grown into a candidate minor arc.

Then **rewrite the whole list once** (`todowrite`) to turn entry 2 into **one line per affected arc**.
For arcs `road-debt` and `lost-mentor` it now reads:

```
Identify affected arcs and threads        — completed
Reconcile arc road-debt                   — pending
Reconcile arc lost-mentor                 — pending
Create any new minor arcs                 — pending
Update the threads dashboard              — pending
Cross-arc / thread consistency sweep      — pending
Report                                    — pending
```

### 2. Reconcile each affected arc — one at a time, expanded just-in-time
Work the arcs top to bottom. For the arc you're on, **expand its one line into the eleven steps**,
work them, then **collapse it back to one line** before starting the next. The list only ever shows
the *current* arc in detail; finished arcs and arcs still ahead stay a single line. (Reminder: each
`todowrite` passes the **whole** list — keep the completed items and the other arcs in it.)

For each affected arc, in order:

**a. Expand it.** `todowrite` the whole list, replacing this arc's single `Reconcile arc <slug>` line
with its eleven steps (all `pending`), and set step 1 to `in_progress`. For `road-debt`:

```
Identify affected arcs and threads        — completed
road-debt · 1 gather what play did        — in_progress
road-debt · 2 turning points              — pending
road-debt · 3 committed answers           — pending
road-debt · 4 key NPCs & factions         — pending
road-debt · 5 premise, conflict & stakes  — pending
road-debt · 6 tension curve & position    — pending
road-debt · 7 engagement paths            — pending
road-debt · 8 hooks to other arcs/threads — pending
road-debt · 9 flip spoiler flags          — pending
road-debt · 10 adjustment log entry       — pending
road-debt · 11 update the state file       — pending
Reconcile arc lost-mentor                 — pending      ← arcs still ahead stay one line
Create any new minor arcs                 — pending
Update the threads dashboard              — pending
Cross-arc / thread consistency sweep      — pending
Report                                    — pending
```

**b. Work the eleven steps** (detailed below), flipping each from `in_progress` to `completed` and the
next to `in_progress` as you go.

**c. Collapse it.** When all eleven read `completed`, `todowrite` the whole list again, replacing those
eleven lines with the single line `Reconcile arc road-debt — completed`. The list is short again, the
next arc still a one-liner. Move to it and repeat from (a).

When every affected arc shows a single `completed` line, this step is done.

The eleven steps, in order:

**1. Gather what play did to this arc.** Read the arc's design + state. From the digest and the
assessment, collect for *this* arc: which turning points landed; which committed answers play
engaged or contradicted; new load-bearing questions play raised; NPCs/factions whose role or
held-answer shifted; what the PC learned that touches this arc (→ now locked); where it sits on its
curve; which engagement path the player took; hooks fired to/from other arcs or threads. That's your
edit list for the steps below.

**2. Reconcile turning points.** Mark which landed (and in which session). Rewrite any beat play
altered to match what actually happened or what now makes sense ahead. Add beats for new turning
points play created; rework or cut ones play made impossible. Every turning point still commits its
answer, `[hidden]` + `Known to`. For *pending* beats the player hasn't reached, redesign freely for
a stronger arc.

**3. Reconcile the committed answers.** For each answer: if the player now *knows* it, it's locked —
keep it verbatim. If play *contradicted* it, recommit a revised answer consistent with what was
played. For each new load-bearing question play raised, commit an answer now. For answers the player
hasn't touched, improve them if it strengthens the arc. Never blank, never "DM decides."

**4. Reconcile key NPCs & factions.** Update the arc's line for each whose role, want, or held-answer
shifted in play — the arc's reference to them and the answer it says they hold — and add any the arc
now leans on as `[[slug]]` links.

**5. Reconcile premise, core conflict & stakes.** Revise toward the story play is actually telling.
If a stake resolved or a new one emerged, write it in. Don't preserve a framing out of inertia — if
play has put a sharper conflict within reach and the player isn't locked into the old one, take it.

**6. Reconcile the tension curve & position.** Update where the arc sits on build-up → climax →
resolution, and re-pace the remaining beats to how fast play is actually moving (accelerate, or
stretch it out).

**7. Reconcile engagement paths.** The legitimately-open part. Reset direct / indirect / avoidance /
alternative to the route the player actually took and the options that now lie ahead from the
current position.

**8. Reconcile hooks to other arcs and threads.** If this arc fired a hook into another arc — or a
thread fed it, or it spun off a thread — update **both** sides' cross-references and the dependency
note, so a minor arc building on the major stays wired to it. Flag any new cross-arc dependency play
created.

**9. Flip spoiler flags for what the PC learned.** For every `[hidden]` fact *in this arc* the PC
learned this session, flip it to `[revealed: S{N}]` and update `Known to`.

**10. Append the Adjustment log entry.** Add one line: **S{N}:** what changed in this arc's
structure/details and the play that prompted it — the provenance of the body's evolution.

**11. Update the arc's state file.** Rewrite `arcs/{slug}.state.md`: Status, Turning points hit
(+ session), Position on the tension curve, `as-of: S{N}`. The state is the quick at-a-glance read;
the body holds the substance.

### 3. Create any new minor arcs play has birthed
If play produced a subplot that deserves real structure (committed answers + turning points), **do
not sketch it ad hoc here** — load the **`arc-design`** skill and author it as a proper minor arc
(`tier: minor`, `hooks-into:` the major), registered in `INDEX`. A lighter lead that isn't yet a
story stays a thread (next step).

### 4. Update the threads dashboard
Reconcile `campaign/state/threads.md` (format: canon-conventions §4): open threads play created,
advance the ones it moved, resolve the ones it closed. Threads are the lighter siblings of arcs —
they feed and spawn arcs — so keep them current here. Promote any that crossed into a real story via
step 3.

### 5. Cross-arc / thread consistency sweep
Confirm every cross-arc/thread hook references both ways, `INDEX` Arc rows are current (status,
one-line), and no arc was left stale or self-contradictory. Verify at least one arc advanced.

### 6. Report
Brief: **Result** (per arc: what changed), **new arcs/threads** created or promoted, **Caveats**
(anything the digest/assessment left ambiguous). No verdict line — the gate (`check-propagation`)
audits this pass separately.

## Boundaries
- Your scope is **arc design bodies, arc state, and the threads dashboard** (and authoring a new arc
  via `arc-design`). Leave entity files, the PC knowledge ledger, and the global `state/*` snapshots
  alone — they're reconciled separately.
