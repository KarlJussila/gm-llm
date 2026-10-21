---
name: state-init
description: Use when writing a new campaign's state before its first session.
---

# state-init

Initialize state from the authored world, character and arcs. Use `canon-conventions` and its
templates. Stamp every initial snapshot `as-of: S0`, the state before play.

- Entity and arc `.state.md` files hold their starting location, condition and activity, or arc
  status and progress.
- `state/current.md` holds the opening scene: where the PC is, when, who's present, the immediate
  situation and opening hook.
- `state/calendar.md` establishes the start date and calendar reference.
- `state/threads.md` records the leads the PC starts with.
- `state/clocks.md` records any time pressure already in motion.
