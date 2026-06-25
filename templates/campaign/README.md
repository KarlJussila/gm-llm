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
| `world/locations.md` | Places — significance, state, hooks, connections | `world-builder`, `dm` |
| `world/npcs.md` | NPCs — personality, motivation, disposition, secrets | `world-builder`, `dm` |
| `world/factions.md` | Factions — goals, members, activity, relationships | `world-builder`, `dm` |
| `world/items.md` | **Significant** objects/artifacts — owner, location, state, history | `world-builder`, `dm` |
| `documents/` | **Verbatim** text of in-world written materials | `dm` (post-session) |
| `characters/{name}.md` | PC sheets — stats, inventory, personality, hooks | `dm` |
| `characters/{name}-knowledge.md` | What the PC **Knows / Believes / Open questions** | `dm` |
| `narrative/arcs/{arc}.md` | Multi-session arcs — turning points, tension, status | `arc-designer` |
| `sessions/session-{N}-plan.md` | The plan for an upcoming session | `session-planner` |
| `sessions/session-{N}-transcript.md` | Raw play transcript, captured automatically | `dm-transcript` plugin |
| `sessions/session-{N}.md` | Structured session digest, extracted from the transcript | `log-extractor` |
| `assessment/session-{N}-assessment.md` | Post-session analysis & arc recommendations | `dm` |
| `feedback/{target}.md` | Distilled player guidance, loaded by the named skill/agent | `dm` |

## How a session is captured

Note-taking is **automatic** — the runner just plays. During the session the full conversation is
recorded to `sessions/session-{N}-transcript.md` by the capture plugin
(`.opencode/plugins/dm-transcript.ts`). After the session the `dm`:

1. delegates to `log-extractor`, which reads the transcript in chunks and writes the structured
   digest `sessions/session-{N}.md` — a lossless extraction of every notable change
   (`log-extract` skill), then
2. applies the digest to canonical state: the knowledge ledger (+`[hidden]`/`Known to:` flags),
   world files, `items.md`, and verbatim `documents/`, and runs the assessment.

Because the transcript is what gets extracted, the rule of thumb during play is **narrate it,
don't just decide it** — document text read aloud, names, and what the character learns must
actually appear in the scene to become canon. See *Knowledge & awareness* below for the
who-knows-what flags.

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
