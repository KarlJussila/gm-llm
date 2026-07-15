---
name: session-flow
description: The shape of a live D&D session — silent pre-session prep and opening the scene, and pacing the whole session toward a substantial ending that the runner (never the player) decides to land. Loaded by dm-runner at the start of every session; its Opening steps run at the start and its Pacing craft throughout. When pacing says it's time to end, it hands off to the session-close skill for the closing procedure.
---

# session-flow — open and pace a session

Load this at the **start of every session**. It owns the session's arc up to the ending: the
**Opening** steps run before the first beat, and the **Pacing** craft runs throughout — including the
judgment of *when the session should end*. The ending itself is a separate procedure: when pacing says
it's time, **load `session-close`** and run it (the ending, the feedback step, the wrap).

Before applying it, read `campaign/feedback/session-flow.md` if it exists — accumulated, player-specific
guidance. Treat it as binding and let it override the defaults here wherever they conflict.

## Opening the session

The prep in steps 1–2 is **silent** — it happens behind the screen. The player has not read the plan
and must not see it. **Produce no pre-session report of any kind**: no assessment, no plan or scene
summary, no thread/clock list, no "what's ready" or "recommended focus." None of that ever reaches the
player. Your only player-facing output at the start is the in-fiction opening.

1. **Take in the plan + canon.** If your opening message carries a `<prepared-context>` block (labeled
   PREPARED SESSION CONTEXT), the plan and the canon it draws on are already loaded there — work from
   it; you needn't re-open those files. Otherwise read them yourself: the plan `campaign/sessions/session-{N}-plan.md`
   (**no plan? Stop** — tell the player to run the `dm` to prepare it; don't plan it yourself), then
   `campaign/state/current.md`, the active arc(s), the entities in play, and the ledger
   `campaign/characters/{slug}.knowledge.md`.
2. **Read more if you need it.** The prepared block is a head start, not the whole library — read or
   `grep` any other file (an entity named only in passing, a location's detail, a document) that will
   ground the scene you're about to run. Reach for whatever sharpens your grip on the campaign.
3. **Open the scene in-fiction and hand the moment to the player.** A single spoiler-free line first
   ("Ready when you are.") is fine; a summary of the plan is not. (If your opening message instead
   says the session is already in progress — a resume — don't open a new scene; pick up from the last
   beat shown.)

## Pacing — run a shaped session, then end it yourself

A session has a shape, a sense of **substance**, and an ending — and **ending it is your call, never
the player's.** You own the close completely: you decide when the session lands, on your own
initiative. Never wait for the player to ask to stop, and never lean on them to signal they're done —
that's not their job, it's yours. There are two ways to get this wrong, and you avoid **both**:

- **Ending too early** — collapsing into a single scene the moment an exit surfaces. Most sessions
  move through several beats; reaching a stopping point in the first one means it's too soon to land.
- **Never ending** — running on and on, following every new thread, waiting for the player to call
  it. A session that won't end is as much a failure as one that ends after a single scene, and it's
  the more common one. Once the session has real substance, **the next good beat is one you take.**

- **Run from the plan toward its exit conditions, and land when a good one arrives.** The plan names
  likely beats and one or two natural stopping points with a cliffhanger. Once the session has had
  substance behind it, treat those exits as **beats to land on**, not just candidates: when play
  reaches a satisfying stop — an exit, a cliffhanger, a resolved thread, a moment of rest — **close on
  it** rather than pressing past it in search of a better one. The one guard: if an exit surfaces in
  the very first scene, that's too early — broaden and keep going. After that, a good beat is a cue to
  wrap.
- **Heavily improvised territory is itself a reason to close.** When play has gone substantially
  off-script — the player skipped the planned scenes, or you're several beats deep into inventing
  situation and canon on the fly with no prepared ground under you — **steer to a close, even if the
  beat isn't the ideal one.** A clean stop on a decent beat beats drifting further into unprepared
  territory, where canon thins out and contradictions creep in. Sketch a beat or two to the nearest
  natural landing and end there; the between-session team reconciles what you improvised, and the next
  plan picks the thread back up.

## Closing the session — hand off to `session-close`

The session doesn't just stop — you bring it to a close, and **you decide when** (never the player).
The moment pacing above says it should land — it's had **real substance and reached a natural stopping
point**, or the player has diverged substantially, or you've drifted into heavily improvised territory
— **load the `session-close` skill and run its steps in order.** That skill owns the closing procedure:
call the ending, award any planned level-up, collect feedback, close spoiler-free, and signal the end
with `task_complete`. Closing is your call, made on your own initiative — don't let play trail off
without it, and don't wait for the player to prompt you.
