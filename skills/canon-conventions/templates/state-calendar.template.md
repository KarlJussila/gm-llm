<!--
  In-game date + event timeline. Path: campaign/state/calendar.md
  Fixes "what's the in-game date?" and "is it market day?" — the runner reads this, never guesses.
  Snapshot as of session <as-of>; updated at POST. Scheduled future events feed clocks.md deadlines.
-->
---
layer: state
as-of: S<n>
---

# Calendar

## Now
<Current in-game date and time of day.>

## Calendar reference
<How time works in this world if non-standard: days of the week, months, seasons, recurring events (market days, festivals, tides). Lives here for the runner's convenience.>

## Timeline — past
<!-- Append-only record of when things happened in-world. -->
| date | event |
|---|---|
| <date> | <what happened> |

## Timeline — scheduled / upcoming
<!-- Known future events; deadline-bearing ones should also appear as a clock in clocks.md. -->
| date | event | clock |
|---|---|---|
| <date> | <what's coming> | <[[slug]] if it drives a clock, else —> |
