---
name: session-close
description: Load when the session has had real substance and a good stopping point is at hand — how to land the ending and close the session.
---

# session-close — end the session

You decide when the session ends; the player never has to ask. Run these in order.

1. **Land the ending.** Close on the beat in front of you — a satisfying resolution or a
   cliffhanger — in the fiction.
2. **Award advancement only if the plan schedules it.** Check the plan's session-end advancement
   line. If it says a level-up lands now, set it in the fiction where it fits and then say it
   plainly: the character has reached level N. The player builds the character in their own tools.
   If the plan says no, don't invent one.
3. **Ask for feedback.** Step out of character and ask a couple of short, open questions about how
   the session felt. Then stop and wait for the answer. Listen; don't argue or fix anything live.
4. **Close.** Thank the player in a line or two, confirming the ending only in the terms they
   experienced it — never what it "means" for the story — and with no preview of what's next.
5. **Signal the end** with one `task_complete` call, as your last act:
   - `player_message` — your closing words to the player (step 4).
   - `notes` — your handoff notes for the between-session pass, below.

## The handoff notes

These are for the campaign's own record, not the player, so be direct, name names, and don't
worry about spoilers. They are the second source beside the transcript — capture what a reader of
the transcript alone would miss. Skip a heading that has nothing under it.

- **Story trajectory** — how the arcs and threads moved, what shifted, where things now point, and
  any clock that advanced.
- **New entities** — every person, place, faction or item that first appeared or was named, with a
  line on each.
- **Changed entities** — anyone or anywhere already in canon whose state, disposition or situation
  changed, and how.
- **The character** — what the PC did, learned, gained or lost; a level-up if one landed.
- **Secrets revealed** — each hidden fact the PC learned, with its `[hidden:<id>]` id where it has
  one.
- **Loose ends** — open questions, promises, dangling hooks, setups awaiting a payoff.
- **Player feedback** — what the player said, verbatim.
