# Campaign files — structure & conventions

This directory is the campaign's whole memory. Every agent reads from here and writes back to
here. The layout below is the contract: each kind of information has exactly one home, so state
doesn't drift or duplicate.

The **authoring format contract** — how every file is structured, named, linked, and flagged — is
the `canon-conventions` skill under `.opencode/`. This README is the orientation map; that skill is
the authority the authoring agents follow.

> **Version control:** this campaign is tracked in its own git repository at the project root,
> separate from the framework (which has its own repository under `.opencode/`). The DM agents
> commit campaign state here with plain `git`; framework code is versioned separately.

## The core distinction: canon vs. state

Most entities (NPCs, factions, locations, items, regions, the PC) live as **two files side by
side**, sharing a slug:

- `{slug}.md` — **canon / info:** who or what it truly *is*. Updated when the underlying truth
  changes.
- `{slug}.state.md` — **state:** where it *is now* (location, condition, what it's doing). A
  **session-boundary snapshot** — accurate at session start, **not edited during play**, rewritten
  afterward by the dm's apply pass. Mid-session, the only live "now" is the transcript.

State files record **narratively significant** state only — not granular mechanics (HP, spell
slots, coin); the player tracks those.

## Directory map

| Path | Holds | Written by |
| --- | --- | --- |
| `INDEX.md` | Registry: every entity → its files, status, one-line. Slug resolver + dedup guard. | `world-builder` (init), `world-keeper`, `dm` |
| `campaign.md` | Overview: premise, tone, themes, content boundaries | `dm` |
| `world/overview.md` · `cosmology.md` · `history.md` | World-truth singletons: premise + hidden layer; how reality works; backstory | `world-builder`, `world-keeper` |
| `world/{npcs,factions,locations,items,regions}/{slug}.md` | Entity **info** (canon) | `world-builder`, `world-keeper` |
| `world/**/{slug}.state.md` | Entity **state** (current snapshot) | `dm` (apply pass) |
| `arcs/{slug}.md` | Arc **design** — premise, turning points, committed answers (a living doc) | `arc-builder`, `arc-keeper` |
| `arcs/{slug}.state.md` | Arc **progress** snapshot — status, beats hit | `dm` (apply pass) |
| `state/current.md` | The "you are here" scene pointer — the runner's resume baseline | `dm` (apply pass) |
| `state/calendar.md` | In-game date + event timeline | `dm` (apply pass) |
| `state/threads.md` | Active leads/threads (a thread spans entities) | `dm` (apply pass) |
| `state/clocks.md` | Time-pressure dashboard — every clock in one place | `dm` (apply pass) |
| `characters/{slug}.md` | PC sheet — stats, personality, backstory, hooks | `dm` |
| `characters/{slug}.state.md` | PC state — location, notable condition, key items, objective | `dm` (apply pass) |
| `characters/{slug}.knowledge.md` | What the PC **Knows / Believes / Open questions** | `dm` (apply pass) |
| `sessions/session-{N}-plan.md` | The plan for an upcoming session | `session-planner` |
| `sessions/session-{N}-transcript.md` | Raw play transcript, captured automatically | `dm-transcript` plugin |
| `sessions/session-{N}.md` | Structured session digest, extracted from the transcript | `log-extractor` |
| `sessions/session-{N}-deltas.md` | Reconciliation log — new canon + arc divergence noted in play | checkers / plugin (during play) |
| `assessment/session-{N}-assessment.md` | Post-session analysis & arc recommendations | `campaign-analyst` |
| `documents/{slug}.md` | **Verbatim** text of in-world written materials | `dm` (post-session) |
| `feedback/{target}.md` | Distilled player guidance, loaded by the named skill/agent | `dm` |

**Not registered in `INDEX.md`:** the world-truth singletons (`overview`/`cosmology`/`history`) and
the `state/*` docs sit at fixed paths; clocks and threads live in their dashboards.

## How a session is captured

Note-taking is **automatic** — the runner just plays. During the session the full conversation is
recorded to `sessions/session-{N}-transcript.md` by the capture plugin
(`.opencode/plugins/dm-transcript.ts`), and the runtime checkers note new canon and arc divergence
to `sessions/session-{N}-deltas.md`. After the session the `dm`:

1. delegates to `log-extractor`, which reads the transcript and writes the structured digest
   `sessions/session-{N}.md` — a lossless extraction of every notable change, then
2. **applies** the digest + deltas to canonical state: the knowledge ledger (flipping
   `[hidden]` → `[revealed: S<n>]`), entity info for new/changed canon, all `*.state.md` snapshots,
   the `state/*` docs, the registry, and verbatim `documents/` — then runs the assessment and
   reconciles each arc.

Because the transcript is what gets extracted, the rule during play is **narrate it, don't just
decide it** — names, read-aloud text, and what the character learns must actually appear in the
scene to become canon.

## Knowledge & awareness

The system tracks **who knows what**, so the DM never confuses what *it* knows (the whole campaign
bible) with what the *character* knows. The rule the runner checks: **the PC knows only what's in
their knowledge ledger, or what is openly perceivable — anything flagged `[hidden]` is off-limits
until revealed.**

Two mirrored layers:
1. **The PC ledger** (`characters/{slug}.knowledge.md`) — the positive record: Knows / Believes /
   Open questions.
2. **Awareness flags** at each fact's home (`world/**`, `arcs/**`): prefix a secret with `[hidden]`
   (→ `[revealed: S<n>]` once learned) and add a `Known to:` line. Openly perceivable details need
   no flag.

```
- [hidden] Lysa feeds the harbor patrol's rotation to the rebel cell.
  Known to: [[lysa-fenn]], rebel leadership.
- [revealed: S2] She knows the cell plans to move on the night tide.
  Known to: [[lysa-fenn]], the PC.
```

At the moment of reveal, update both layers in the same beat (ledger line + flag flip). Full detail
is in the `canon-conventions` skill.

## Player feedback loop

The runner collects player feedback at session end (recorded in the digest). The `dm` distills it
into `feedback/{target}.md` files, which the matching skill or agent loads as binding guidance —
baking feedback into behavior without editing the framework. See `feedback/README.md` for routing.

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

## Git workflow

Commit messages follow the pattern:
- `campaign: init` — initial setup
- `campaign: session N plan` — pre-session planning
- `campaign: post-session N updates` — post-session reconciliation
- `campaign: [description]` — other changes
