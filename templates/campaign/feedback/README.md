# Player feedback — accumulated guidance

These files turn the player's session-to-session feedback into durable guidance that shapes how
the system behaves, **without editing the framework** (the skills and agents under `.opencode/`
stay campaign-agnostic and reusable). Each file is loaded by the skill or agent it's named after
and treated as binding, player-specific guidance that overrides the defaults in that skill/agent.

## How the loop works

1. **Collect (dm-runner, at session end).** The runner asks the player for feedback and records
   their answers *verbatim* in the session log under "Player feedback." It does not act on it
   live or argue — just captures.
2. **Distill (dm, between sessions).** During post-session review the `dm` reads that feedback
   and integrates each item into the matching file below — refining existing guidance, removing
   what's been superseded, keeping each file a tight list of *current* standing guidance (not a
   raw transcript).
3. **Apply (everywhere).** Each skill reads its own feedback file at the start of its work; the
   two primary agents read their agent-level file at startup. Guidance here wins over defaults.

## Routing — which file gets the feedback

Prefer **skill-level** files; they're reused across every agent that loads the skill. Use an
**agent-level** file only for conduct that isn't governed by a skill.

| File | Governs |
| --- | --- |
| `session-run.md` | Core live DM craft applied every turn: player agency, rolls, spoiler discipline, tone |
| `session-flow.md` | Opening, pacing, and closing a session — including end-of-session feedback |
| `social-play.md` | Conversations and NPCs: show-don't-tell, Insight-gating, Charisma checks, NPC agency |
| `discoveries.md` | Revealing information: expert synthesis, gating discoveries behind the right check |
| `session-plan.md` | How sessions are prepared: over/under-planning, content mix, structure |
| `campaign-setup.md` | New-campaign flow: stage ordering, premise/hook presentation, pacing of setup |
| `campaign-intake.md` | Opening brief: how much to ask, free-form vs. guided, content-boundary handling |
| `character-create.md` | Character creation: how collaborative, depth of backstory, mechanical help |
| `character-import.md` | Parsing imported character files: where the player's sheets keep fields, what to grab |
| `arc-design.md` | Story/arc feel: railroading, stakes, pacing across sessions |
| `world-build.md` | World/NPC/faction quality: depth, consistency, friction |
| `dm-runner.md` | Runner conduct not in a skill (e.g. too much out-of-character talk) |
| `dm.md` | Orchestrator conduct: spoiler discipline, delegation, commit cadence |

Files are created on demand — there's no need to pre-create empty ones. If a file doesn't exist,
there's simply no accumulated feedback for that target yet.

## Entry format

Keep each file a short list of standing guidance. For each item, state the guidance and a brief
why, and note the session it came from. Example:

```
- **Make information hard-won — ask for rolls on uncertainty.** The player wants discovery to
  feel earned, not gifted. (from S2)
- **Don't narrate the character's actions or decisions.** Player declares; DM adjudicates;
  clarify when ambiguous. (from S2)
```
