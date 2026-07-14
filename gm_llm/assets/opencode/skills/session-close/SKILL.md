---
name: session-close
description: The procedure for ending a live D&D session — call the ending, award any planned level-up, collect player feedback, close spoiler-free, and signal the end with task_complete. Loaded by dm-runner when session-flow's pacing says it's time to land the session (the runner owns that timing, never the player). session-flow decides WHEN to close; this skill is HOW.
---

# session-close — end the session

Load this the moment **session-flow's Pacing** tells you the session should land — it's had real
substance and a good beat has arrived, the player diverged substantially, or play has drifted into
heavily improvised territory. **You decide when to close; the player never does** — that judgment is
session-flow's, and you act on it here on your own initiative, never waiting to be asked. This skill is
the *how*: the closing procedure, run **in order, every session**. Don't let play trail off without it.

Before applying it, read `campaign/feedback/session-close.md` if it exists — accumulated,
player-specific guidance on how sessions should land. Treat it as binding and let it override the
defaults here wherever they conflict.

## The closing steps — in order, every session

1. **Call the ending yourself.** When the session has substance and a good beat arrives, land it — a
   satisfying beat or a cliffhanger — on your **own initiative**. **Never wait to be asked**: the
   player doesn't close the session, you do, and a session that keeps running because you're waiting
   for their cue has failed. The one floor: a single-scene session almost never has the substance yet,
   so don't wrap on the first beat. Past that, take the good beat when it comes rather than holding out
   for a perfect one.
2. **Award advancement if the plan calls for it.** Check the plan's **Session-end advancement** line.
   If it schedules a level-up this session, hand it to the player as the session lands — set it in the
   fiction where it fits, then say it plainly: their character has reached level N. Leave the actual
   building/balancing to the player and their D&D tools (the system doesn't build sheets); you're just
   marking that it happened. **Only award what the plan schedules** — if the plan says no level-up, don't
   invent one, and never change the target level yourself.
3. **Collect feedback.** Step out of character; ask the player a couple of short, open questions about
   the session. Listen — don't argue or fix it live. **This step is not optional and not silent — it
   happens at the end of every session.**
4. **Close spoiler-free.** Confirm the ending beat only in the terms the player experienced it —
   never characterized in terms of the campaign's design ("a turning point," what it "means" to the
   arc). That hands the player the shape of the plot — exactly what spoiler discipline exists to
   protect — whether said in-fiction or as plain fact. Thank them, and stop. No summary, no preview
   of what's coming.
5. **Signal the end.** As your very last act — after closing out — **call the `task_complete` tool**.
   That hands the session back to the campaign team to wrap up (their between-session work reads your
   handoff notes and reconciles canon). Only call it once steps 1–4 are done; never mid-scene.
