# Campaign files — structure & conventions

This directory is the campaign's whole memory. Every agent reads from here and writes back to
here. The layout below is the contract: each kind of information has exactly one home, so state
doesn't drift or duplicate.

> **Version control:** this campaign is tracked in its own git repository at the project root,
> separate from the framework (which has its own repository under `.opencode/`). The DM agents
> commit campaign state here with plain `git`; framework code is versioned separately.

## Directory map

| Path | Holds | Written by |
| --- | --- | --- |
| `campaign.md` | Overview: premise, tone, themes, session history | `dm` |
| `world/locations.md` | Places — significance, state, hooks, connections | `world-builder`, `dm-runner` (live) |
| `world/npcs.md` | NPCs — personality, motivation, disposition, secrets | `world-builder`, `dm-runner` (live) |
| `world/factions.md` | Factions — goals, members, activity, relationships | `world-builder`, `dm-runner` (live) |
| `world/items.md` | **Significant** objects/artifacts — owner, location, state, history | `world-builder`, `dm-runner` (live) |
| `documents/` | **Verbatim** text of in-world written materials | `dm-runner` (live) |
| `characters/{name}.md` | PC sheets — stats, inventory, personality, hooks | `dm` (setup), `dm-runner` (live state) |
| `characters/{name}-knowledge.md` | What the PC **Knows / Believes / Open questions** (live) | `dm` (setup), `dm-runner` (live) |
| `narrative/arcs/{arc}.md` | Multi-session arcs — turning points, tension, status | `arc-designer` |
| `sessions/session-{N}-plan.md` | The plan for an upcoming session | `session-planner` |
| `sessions/session-{N}.md` | The factual log of what actually happened | `dm-runner` |
| `assessment/session-{N}-assessment.md` | Post-session analysis & arc recommendations | `dm` |
| `feedback/{target}.md` | Distilled player guidance, loaded by the named skill/agent | `dm` (from runner's capture) |

## Capture conventions (for `dm-runner` during live play)

Record at the **moment** a thing is created or changes — exact text and details cannot be
reconstructed after the session.

- **Verbatim documents.** The instant any written text is shown to the player — a letter, journal,
  inscription, sign, contract, book passage, or an overheard line whose exact wording matters —
  write it word-for-word to `documents/{slug}.md`. Do not paraphrase; the player may quote it back
  three sessions later. (Hard lesson: an official journal in the test campaign was only ever
  paraphrased, and its text is now lost.)
- **Improvised canon.** The moment you invent something reusable — a name, a place, a rumor, a
  custom, a minor NPC, a faction detail — write it to the matching world file so it becomes canon
  and stays consistent. Improvisation that isn't recorded evaporates.
- **Item & object changes.** Anything the party gains, loses, consumes, gives away, leaves behind,
  or alters: update the right home. Significant objects → `world/items.md`. A PC's ordinary gear →
  that character's sheet. One home each — never two parallel lists.
- **Knowledge changes.** The moment the PC learns, suspects, or is told something, update
  `characters/{name}-knowledge.md` (add to Knows / Believes / Open questions) **and** flip the
  source fact's flag (`[hidden]` → `[revealed: S<n>]`, adding "the PC" to its `Known to:`). When an
  NPC learns something (e.g., the PC tells them), add that NPC to the fact's `Known to:`. See
  *Knowledge & awareness* below.

## Knowledge & awareness

The system tracks **who knows what** so the DM never confuses what *it* knows (the whole campaign
bible) with what the *character* knows. The rule the runner checks: **the PC knows only what's in
their knowledge ledger, or what is openly perceivable in the scene — anything flagged `[hidden]`
is off-limits until revealed.**

**1. PC knowledge ledger — `characters/{name}-knowledge.md`** (the live, consolidated *positive*
record; the runner's first read each session):

```
# {Name} — what they know

## Knows
- <established fact the PC holds as true>   (learned S<n>)

## Believes (may be wrong)
- <belief or suspicion, including misinformation the PC accepts>   (S<n>)

## Open questions
- <a known unknown the PC is aware of and may chase>   (raised S<n>)
```

**2. Awareness flags on facts** (the *negative* space, stored at each fact's home in
`world/*.md` and `narrative/arcs/*.md`). Tag each significant secret or reveal-able fact:

- `[hidden]` — the PC does **not** know this. `[revealed: S<n>]` — the PC learned it in session n.
- `Known to:` — the in-world parties aware of it (NPCs, factions, and "the PC" once revealed). If
  omitted, assume only the entity it concerns knows. This is what lets NPCs act on what they
  actually know, and lets information spread.

```
## Maren Blackthorn
Former Dominion intel; hunting Archive research.        ← openly apparent (no flag needed)
- [hidden] Unbound operative; wants to accelerate the seal's collapse.
  Known to: Maren, Unbound leadership.
- [revealed: S1] She knows the name Vaelith.
  Known to: Maren, the PC.
```

Openly perceivable details need no flag — they're known once encountered. Flags are for secrets,
true natures, hidden motives, and planned reveals. At the moment of reveal, update both layers in
the same beat (ledger line + flag flip).

## Player feedback loop

The runner collects player feedback at session end (recorded verbatim in the session log). The
`dm` distills it into `campaign/feedback/{target}.md` files, which the matching skill or agent
then loads as binding guidance. This bakes feedback into behavior without editing the framework.
See `feedback/README.md` for routing and format.

## Document file format (`documents/{slug}.md`)

```
# {Title or description}

- **Type:** letter | journal | inscription | sign | book | contract | note
- **Found:** where/when/how the party encountered it (session N)
- **Author / provenance:** who wrote it, if known
- **Status:** held by whom, or where it now is

## Text

> The exact text, recorded verbatim as the player received it.
```

If a document is partially legible, damaged, or encoded, record exactly what is readable and note
the gaps — don't fill them in.

## Item entry format (`world/items.md`)

Each significant object: name, what it is, current owner/location, current state, and a short
history of how its state has changed. Mundane gear stays on character sheets.
