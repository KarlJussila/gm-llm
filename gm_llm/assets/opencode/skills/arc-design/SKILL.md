---
name: arc-design
description: Load when designing a new arc — the campaign's major arc or a minor arc hooked into it.
---

# arc-design

The campaign has one major arc and minor arcs that hook into it.

- **The major arc** is the spine, `tier: major`. Its central conflict is personal: built on this
  PC's backstory, goals and bonds, so it matters to this character.
- **A minor arc** is a focused subplot, `tier: minor`, with `hooks-into:` set to the major. It earns
  its place by feeding the major — escalating its clock, exposing one of its answers, complicating
  its conflict — and the cross-references run both ways.

## Commit every answer

Planning and play pull their answers from the arc; an answer the arc leaves open gets invented
downstream, differently each time. So every turning point commits its reveal, identity or
consequence, tagged `[hidden:<id>]`, and every question the campaign will raise that matters to the
plot has its answer in the committed-answers section. The arc owns who its NPCs really are: nothing
downstream casts a second identity for a role it filled. Only the player's path stays open — that's
what the engagement paths are for.

## What a strong arc has

Fill the template's sections:

- **Premise and core conflict** — a real tension, and what concretely happens if it goes unresolved.
- **Opposition** — every story needs conflict, whatever mix of play the player wants: someone whose
  wants work against the PC's, and who acts on them. A mystery, a disaster or a broken system can
  be the stakes, but give it people too — someone who caused it, profits from it, or will stop the
  PC from fixing it.
- **Stakes that bite** — a concrete cost tied to what the PC cares about. How the arc uses their
  backstory stays behind the screen.
- **Key NPCs and factions** — named, each with a committed identity and a want. Cast from the
  world's people where one fits and create the ones the arc still needs (`create_entities`): its
  antagonist, allies, informants and go-betweens are people, not offices.
- **Turning points**, three to five. A turning point is where the story's situation changes,
  through a revelation, reversal or escalation, after which the PC wants something different,
  faces something new, or can do something they couldn't before. It's the world moving or a truth
  coming out, never a step in the PC's own work. Each commits its answer and says how it's likely
  to reach the table: a fight, an investigation, a negotiation, a heist, a journey.
- **Tension curve** — build-up, rising action, climax, falling action, resolution, with the kinds
  of play each stretch calls for, mixed the way the player's brief asks. Flat too long bores;
  spiking too often burns out.
- **Engagement paths** — direct, indirect, avoidance, alternative: how the player might come at it,
  and how it escalates on its own if ignored.
- **A hook** that draws the player in naturally — a bond, curiosity, urgency, a moral obligation.
- **Cross-arc dependencies**, flagged, so the arcs can be coordinated; intersections force harder
  choices.

Start from what the PC actually knows (the knowledge ledger), and record who's in on each secret
with `Known to:`.

## Craft

- **Conflict escalates.** The opposition notices what the PC does and answers it, and the pressure
  rises along the curve. When words stop working or the stakes turn physical, the conflict comes to
  blows — a fight is where a conflict lands, not a break from the story.
- **Mysteries pay off.** Every question the arc raises leads somewhere the PC can reach, and each
  answer opens the next question. Clues point forward.
- **Make it personal.** The stakes land on what the PC cares about, and the hard choices are
  between things they want.
- **Choices cost something.** Give the PC dilemmas, not only puzzles: each way forward gains
  something and gives something up.
- **The world doesn't wait.** Ignored, the opposition advances and the cost grows.

## Level pacing

The major arc owns the advancement schedule, in its *Level pacing* section; a minor arc has none.

- **Milestone levelling, at a session's end** — never mid-scene.
- **Every two to five sessions, scaled by level:** about every two at low levels, every four or five
  by the teens. Pace from the PC's current level.
- **Prefer a beat, keep the cadence.** Land a level-up just after a major turning point when one is
  near, but the cadence holds when none is: never stall levelling for want of a beat, and never
  bunch two together to catch up.
- **Commit each milestone:** the target level, the session it's due, and the beat it rides on when
  there is one.

## Before you write

Read `campaign/campaign.md` and `world/overview.md`, the world and `INDEX.md` (to reuse entities,
not duplicate them), the PC's sheet and ledger, and the existing arcs so a new one complements
rather than collides — for a minor arc, above all the major it hooks into. Write `arcs/<slug>.md`
and its `.state.md` from the templates in `canon-conventions`.
