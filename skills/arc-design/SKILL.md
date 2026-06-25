---
name: arc-design
description: Design new narrative arcs or revise existing ones for a D&D campaign. Use when creating a story arc (premise, turning points, tension curve, engagement paths) or when adjusting an arc's trajectory after a session based on what players actually did. Produces or updates a single arc document.
---

# arc-design

## Player feedback — read first

Before designing or adjusting, read `campaign/feedback/arc-design.md` if it exists. It holds
accumulated, player-specific guidance distilled from past sessions. Treat it as binding and let it
override the defaults here wherever they conflict.

One skill, two modes. **Designing** creates a new arc document. **Adjusting** revises an
existing one after play. Both produce a single arc file written so it stays easy to update.

An arc document answers: *What is this story about, what is at stake, and how might it unfold
across sessions?*

## Input

Before working an arc, gather:

- **Campaign overview** — setting, tone, themes, current timeline (`campaign/campaign.md`)
- **Existing arcs** — their status and trajectory (`campaign/narrative/arcs/`)
- **Player characters** — backgrounds, goals, bonds, unresolved threads (`campaign/characters/`)
- **World state** — current political, social, magical conditions (`campaign/world/`)
- **Recent sessions / assessments** — what just happened that feeds this arc

---

## Mode A — Designing a new arc

Every arc document contains these sections:

### 1. Name and Premise
A short name and a one-paragraph premise in plain language — what the arc is about, why it
matters, what makes it interesting.

### 2. Key NPCs and Factions
For each: name and role (antagonist, ally, neutral), motivation (what they want and why),
relationship to the core conflict.

### 3. Core Conflict and Stakes
The central tension. What happens if the players fail to resolve it. Stakes must be tangible
and meaningful to these characters — tie them to goals, relationships, or the world the player
has invested in. Abstract stakes feel hollow.

### 4. Planned Turning Points
3–5 major beats that move the arc forward. Each should shift direction, raise or lower tension,
introduce new information/threats/opportunities, and be keyed to a session or milestone where
possible.

### 5. Tension Curve
Map the pacing: build-up (clues, rising stakes) → rising action (complications, partial
victories) → climax (peak confrontation or revelation) → falling action (aftermath,
consequences) → resolution (closure or bridge to the next arc).

### 6. Multiple Engagement Paths
- **Direct** — they take the hook and pursue it head-on
- **Indirect** — they stumble into it via side quests or exploration
- **Avoidance** — what happens if they ignore it? How does it escalate on its own?
- **Alternative solutions** — resolutions that differ from the intended path

### 7. Current Status
`dormant` (not yet introduced) · `building` (hooks in play, tension rising) · `climax` (at its
peak) · `resolved` (complete, consequences in effect).

### 8. Links
Related arcs, sessions tied to this arc, relevant NPCs / locations / items.

### Design principles
- **Every arc needs a hook** that draws players in naturally — bond, curiosity, urgency, moral
  obligation. Never force engagement.
- **At campaign setup (or when a new PC joins), make at least one major arc personal.** Weave it
  into the character's backstory hooks and goals (a loss, a hunted past, a rival, a debt) so the
  central conflict matters to *this* character. Keep how the arc exploits their backstory
  spoiler-side — the player should feel the pull without seeing the plan.
- **Flag the arc's secrets and track who's in on them.** Turning points, the central truth, and
  villain motives are spoilers: mark them `[hidden]` and add a `Known to:` line naming the NPCs or
  factions aware of each (see `campaign/README.md` → *Knowledge & awareness*). When framing the
  hook, be explicit about what the PC currently knows versus what's hidden — cross-check the PC
  knowledge ledger (`characters/{name}-knowledge.md`) so the arc starts from what they actually
  know.
- **Leave room for agency.** The plan is a direction, not a script. If players go off-track,
  adapt the arc rather than railroad them.
- **Track tension to avoid stagnation or fatigue.** Flat too long = boredom; spiking too often =
  burnout. Pace deliberately.
- **Arcs can run parallel or intersect.** Intersections force harder choices and richer moments.

---

## Mode B — Adjusting an existing arc

Read the affected arc plus the latest session log and assessment before changing anything.

### Evaluate first
1. **Engagement** — did players engage? How actively? Pursue it, or stumble in?
2. **Direction** — did they take it somewhere unexpected? Original trajectory vs. what happened.
3. **Consequences** — what unintended consequences resulted? Did anything resolve prematurely or
   create new complications?
4. **Relevance** — is the arc still relevant, or superseded by something more pressing?

### Classify the adjustment
- **Accelerate** — progressing faster than expected; move turning points up, compress build-up.
- **Decelerate** — hasn't landed yet; add intermediate beats, deepen complications.
- **Redirect** — player actions changed direction; follow their lead, preserve core themes.
- **Merge** — player actions connected this arc to another; consider unifying them.
- **Shelve** — no longer relevant; mark dormant or resolved. It may resurface later.
- **Emergency** — something broke the arc (plot hole, contradiction); creative repair.

### Then update the arc document
Revise turning points, tension curve, engagement paths, and status. Add a short **Adjustment
log** entry: what changed and why, dated to the session that prompted it.

### Adjustment principles
- **Preserve player agency.** Adapt to their choices; never reverse their impact or negate
  meaningful decisions.
- **Maintain internal consistency.** Don't retcon established events — build forward from what
  happened.
- **Flag cross-arc dependencies.** If an adjustment requires changes to other arcs, say so
  explicitly so the DM can coordinate.

---

## File output

Write to `campaign/narrative/arcs/{arc-name}.md` using kebab-case
(e.g. `the-iron-covenant.md`). When adjusting, update the existing file in place.

## Tone
Creative, structured, forward-thinking. Arcs are living documents — prioritize clarity and
usefulness over prose polish.
