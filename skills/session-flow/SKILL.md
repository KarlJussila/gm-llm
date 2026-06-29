---
name: session-flow
description: The shape of a live D&D session from open to close — silent pre-session prep and opening the scene, pacing the whole session toward a substantial ending, and closing it (propose the ending, collect player feedback, wrap spoiler-free). Loaded by dm-runner at the start of every session; its Opening steps run at the start and its Closing steps at the end.
---

# session-flow — open, pace, and close a session

Load this at the **start of every session**. It owns the session's arc: the **Opening** steps run
before the first beat, the **Pacing** craft runs throughout, and the **Closing** steps run at the end
— including collecting feedback, which happens every session and is easy to forget.

Before applying it, read `campaign/feedback/session-flow.md` if it exists — accumulated, player-specific
guidance. Treat it as binding and let it override the defaults here wherever they conflict.

## Opening the session

The prep in steps 1–2 is **silent** — it happens behind the screen. The player has not read the plan
and must not see it. **Produce no pre-session report of any kind**: no assessment, no plan or scene
summary, no thread/clock list, no "what's ready" or "recommended focus." None of that ever reaches the
player. Your only player-facing output at the start is the in-fiction opening.

1. **Take in the plan + canon.** If your opening message carries a **PREPARED SESSION CONTEXT** block,
   the plan and the canon it draws on are already loaded there — work from it; you needn't re-open
   those files. Otherwise read them yourself: the plan `campaign/sessions/session-{N}-plan.md`
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

## Pacing — run a shaped session and end it

A session has a shape, a sense of **substance**, and an ending. It does **not** run until the player
asks when you'll stop — but it also does **not** collapse into a single scene the moment an exit
condition happens to surface. Most sessions move through several beats; reaching a stopping point in
the first one means it's too early to land, not time to wrap.

- **Run from the plan toward its exit conditions — but pace the whole session, not just the exit.**
  The plan names likely beats and one or two natural stopping points with a cliffhanger. Treat the
  exits as *candidate* landings, **not magnets**. An exit is a real ending only once the session has
  had enough substance behind it. **If an exit beat lands early** — the player beelines to the one
  NPC or moment that triggers it — that's a signal there's *room to keep going*, not a cue to stop:
  broaden the scene, follow what it opens up, or move to the next beat.
- **When the player goes substantially off-script** (e.g., they ally with the antagonist and skip
  the planned scenes), don't just keep improvising open-endedly. Pause, sketch a **short forward
  plan** — two to four beats to a fresh, natural stopping point — and play toward that exit.

## Closing the session

The session doesn't just stop — you bring it to a close. When pacing tells you it has had **real
substance and reached a natural stopping point** (or the player has again diverged substantially), run
these three steps **in order, every session** — don't let play trail off without them:

1. **Propose the ending yourself.** Land on a satisfying beat or a cliffhanger — don't wait to be
   asked, and don't end early just because an exit surfaced. A single-scene session almost never
   qualifies yet.
2. **Collect feedback.** Step out of character; ask the player a couple of short, open questions about
   the session. Listen — don't argue or fix it live. **This step is not optional and not silent — it
   happens at the end of every session.**
3. **Close spoiler-free.** Confirm the ending beat, thank them, and stop. No summary, no preview of
   what's coming.
