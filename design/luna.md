# Luna — gm-llm rebuilt for GPT-6 Luna

Plan of record for the product rebuild. The benchmark that measures it is
[benchmark.md](benchmark.md); the combat tracker and loop design is [combat.md](combat.md).
Sequencing lives in `ROADMAP.md` track **luna**.

## Outcome

gm-llm runs setup → play → reconcile on `openai/gpt-6-luna` at `xhigh` reasoning, with prompts
written for a capable model instead of around a weak one's failures.

**MiMo is retired.** v0.5.0 (tagged) is the last MiMo release. `mimo-v2.6-flash-free` may be run as
a benchmark subject against the new product, but it is never used to build it. There is no
backwards compatibility with v0.5 campaigns; the fixture is converted by script.

The Part 11 probe ran on `gpt-5.6-luna-fast`. The 5.6 and 6 generations behave alike, and the
`-fast` variants only change output speed, so its observations carry over: Luna paced and wrapped a
session unprompted, looked canon up on its own, and followed rules exactly as stated (including a
wrong one the probe prompt gave it).

## Principles

1. **Luna everywhere unless named.** Every agent and subagent is `openai/gpt-6-luna` at `xhigh`.
   The one exception so far is the benchmark grader ([benchmark.md](benchmark.md)). Luna does not
   accept a temperature; agent files set a reasoning `variant` instead.
2. **No per-turn reminders.** No brief prepended to every message, no staleness counts, no wrap
   countdown. Standing guidance lives in the agent prompt and is read once.
3. **Skills stay; loading is the model's call.** A skill's `description` says briefly *when* to load
   it, never a summary of what it contains. No brief names the skills to load or their order. A rule
   that applies on every turn belongs in the agent prompt, not in a skill that is always loaded.
   Each agent's permissions allow only its own skills, so its catalog lists nothing else — not
   another agent's, not the player's own.
4. **No instructed choreography.** No brief or skill tells the model to build a todo list or work
   numbered steps in order. `todowrite` stays *permitted* — the model may plan with it.
5. **Turn checks never reach the DM.** Live play has no gate. Turn checks run after play, in the
   benchmark only.
6. **Tool-call help stays.** A missing or malformed tool call gets one nudge (`Backend.ensure_tool`).
   That is mechanics, not hand-holding.
7. **Code owns the copies.** Anything derivable — the registry, reveal flags, which arcs were
   reconciled — is derived or verified in code, not hand-maintained by the model and audited by a
   checker.
8. **Between-session gates must earn their place.** `check-digest`, `check-propagation`, `check-plan`
   and `check-init` stay for now, and each archives its artifact before and after correction. A gate
   that rarely makes a meaningful correction is cut.
9. **Subagents are a tool the dm may use.** The dm may delegate through opencode's `task` tool to
   our own subagent definitions, pinned to Luna (never opencode's built-in `general`).
   One `task` call blocks; several in one message run concurrently. A user setting
   `subagents: sequential | parallel` becomes one sentence in the brief — sequential by default, the
   safe choice for rate-limited free models. Subagent calls are captured in the archive and token
   counts.
10. **Player feedback belongs to the player.** It lives in a player-level directory shared across
    campaigns, one file per audience: `dm-runner.md` for the table, `dm.md` for the work between
    sessions. Code hands each to its agent — the runner's in its prepared context, the dm's ahead of
    the first brief on each dm thread, which the dm passes on to its authors — so no agent looks
    feedback up. The agents can't reach outside the project, so they work on the project's
    `feedback/`: code fills it from the player's directory and copies back what curation changed. Benchmark runs point it at the run's private copy of
    the fixture's feedback. Configuration is documented in
    [Player settings](../README.md#player-settings).

## Agents

| Agent | Role | Model-facing change |
|---|---|---|
| `dm-runner` | Live play: read-only campaign access, dice, the combat tracker, `task_complete` | New prompt (see § Live play) |
| `dm` | Between sessions: setup, reconcile, planning; writes the campaign | Briefs state goals, not skill sequences; may delegate to subagents |
| `log-extractor` | Fresh-context digest of the transcript | Whole-transcript read |
| `helper` | General-purpose subagent for the dm's delegated work, pinned to Luna | New |
| `narrative-checker` | Between-session gates, and the benchmark's after-play checker | Re-authored for Luna; never at the table |
| `player` | The benchmark's player | See [benchmark.md](benchmark.md) |
| `auto-player` | The autonomous player (`--player auto`) | New (see § Autonomous play) |
| `setup-player` | Answers setup from the player's script (`play --setup-script`) | New |

`campaign-analyst` and the `session-review` assessment are deleted; feedback curation moves to the
`dm` thread.

## Campaign layout

- **`INDEX.md` is generated** by code from each file's frontmatter (`slug`, `name`, `type`, `status`,
  `summary`; arcs add `tier` and `hooks-into`). The model reads it to avoid duplicates and never
  writes it.
- **Vitals move into YAML frontmatter**, with a schema per entity type. The body stays prose.
- **Secrets carry ids:** `[hidden:<id>]`. A reveal is recorded once, by id, in the PC's knowledge
  ledger; code flips the flag in the home file and adds the PC to its `Known to:` line.
- **One folder per session:** `sessions/<n>/{plan,transcript,notes,digest}.md`, and session 1's
  `prologue.md`.
- `.state.md` stays a separate file per stateful entity.
- `assessment/` is gone, and `feedback/` leaves the campaign (principle 10).
- **The canon lint** (code) runs after every authoring dispatch: frontmatter schema, links resolve,
  no lingering `named-only`, `as-of` stamps current, secret ids resolve. Its findings go back once,
  as a correction.
- `canon-conventions` is rewritten as a reference for this layout.
- **Anyone of consequence is named and filed** as soon as it is apparent they will matter: a
  recurring contact, a faction's leader, anyone an arc or thread leans on. An NPC file starts as a
  shim — vitals, who they are, what they want, how they come across — and grows as the NPC gains
  weight: stats only for someone who may fight, a hidden layer only where there is one. A plugin
  tool scaffolds entity files and their state files from frontmatter values, so the model writes
  only the prose. Extras the runner invents and never meets again stay unnamed.
- **Threads are the leads beside the arcs** (`state/threads.md`): local problems, hooks, people with
  wants. One the player takes up and that proves compelling is promoted to a minor arc in the arc
  close-out.
- **Every file keeps its purpose.** The session's record is its digest; other files hold only the
  result. The knowledge ledger is what the PC knows of the world now, kept by subject and rewritten
  as play changes it — never what the PC did, planned or rolled. An arc is the design of a story
  ahead and what is true beneath it, never a recap of play; where it stands is its state file.

## Setup

1. **Scaffold** — code.
2. **Intake and pitch** (interactive). The DM gathers the brief (free-form or guided; lines and
   veils), writes `campaign.md`, and pitches the world as an ordinary message: premise, tone, the
   shape of the world and where the PC would begin. Conversation only; the world is built next. The
   player can push back and the DM revises. When the player approves, the DM calls `task_complete`.
3. **World** — one non-interactive dispatch, subagents allowed. The world is built top down, each
   tier to its own depth, so its details trickle down to where the PC begins:
   - **The world, in broad strokes:** countries and powers, important cities, factions and the
     geopolitics between them; peoples, faiths and magic as they shape society; a history with
     named eras and events.
   - **The region, in structure:** its geography and political structure — settlements, routes,
     who holds power and who contests it, its neighbours.
   - **The vicinity, in fine detail:** where the PC begins, with NPCs and locations to interact
     with, what is happening there now, and problems of its own beside the main story.

   The brief says what to populate and what to flesh out, never how many: the model judges the
   amount.
4. **Character** (interactive, same thread). Code sends the character brief; the DM opens with hooks
   drawn from the built world and the creation choice, imports a sheet if given one, fills the
   vitals, agrees backstory and placement with the player, writes the PC files and any backstory
   canon, then calls `task_complete`. The knowledge ledger starts with what someone of the PC's
   background knows of each tier.
5. **Arcs and state** — one non-interactive dispatch. The major arc built around the PC (with its
   level pacing), at least one minor arc hooked into it (subagents optional), the threads, and
   initial state. Arcs are built on named NPCs, and an arc spins out the new NPCs it needs. The
   vicinity's problems become threads. Last comes the spoiler-free **player primer**,
   `documents/primer.md`: the world, the region and the vicinity as the PC knows them before play,
   from their background and ledger, foregrounding what the arcs will draw on. It waits until here
   because only now is it known who the PC is and what will matter. Code then verifies one major arc, at least one minor arc with
   `hooks-into`, state stamped `S0` and the primer (`as-of: S<n>` means as of the end of session n, so state
   before play is `S0`), with one nudge naming anything missing. Resume reads the same disk facts.
6. **Canon lint** — one correction.
7. **`check-init`** — the judgment half only: duplicates, consistency with `campaign.md`, and
   coverage — each tier built to its depth, the vicinity populated, the arcs cast with named NPCs.
   One correction.
8. **Commit** `campaign: init`; code points the player to their primer. Then **plan session 1**
   (§ Planning) at once; the player is asked before it opens.

A setup script (`play --setup-script`) puts the `setup-player` agent in the player's seat for the
interactive stages; its format is in the README.

`campaign-setup` is deleted; its standards are either in `canon-conventions` or are now the lint.

## Live play

**Start.** Code builds `<prepared-context>`: the plan, the PC's sheet, state and knowledge ledger,
a map of `campaign/` (the `INDEX.md` tables, then every file they don't list), and the player's
feedback. Its header is one plain sentence: this is your prepared context; everything else is on
disk. The runner reads the people, places and arcs a scene turns on as it needs them; preloading
them all taught it to answer from what it had. The opening is not checked. In session 1, code reads
the prologue out verbatim ahead of the opening, and writes it first in the transcript; the runner gets
it after its prepared context and opens where it ends.

**Each turn.** The message is the player's text in `<player>…</player>` and nothing else. Code keeps:
the completion marker on `task_complete`, the one nudge for an ending narrated without the tool,
the switch into combat, the transcript, and the archive (player message, reply, tools, context size).

**The `dm-runner` prompt** holds, from the start of the session:

- the role and its boundaries, and spoiler discipline tested against the knowledge ledger;
- the table craft that was `session-run` (the player declares and the DM adjudicates; the delivery
  carve-out; stepping out of game on the impossible; the player rolls their own checks; ask for rolls
  often; never announce a DC; outcomes on a gradient) — your play preferences, condensed;
- how to open a session;
- pacing: what a good stopping point is, the two failures (ending after one scene, never ending),
  and that play drifted far from anything prepared should start looking for one. Ending is the DM's
  call.

On-demand skills: `social-play`, `discoveries`, `session-close`, `combat-run` ("when a fight is about
to start") and `combat-balance`.

**Ending.** The DM loads `session-close`: land the ending, award the level-up the plan schedules,
ask the player for feedback, close without spoilers, then make one `task_complete` call carrying
the handoff notes in `notes` — its closing narration is its reply text, like any turn's.
`session-close` says what the notes cover. Code writes the narration into the transcript and the
notes to `sessions/<n>/notes.md`. A separate notes request is the fallback only when they come
back missing.

**The reply is the player's screen.** Every agent's rules state the one rule: reply text reaches
the player verbatim and unfiltered — the player-facing words go there and nowhere else, spoilers
never go there, and behind-the-screen work stays in reasoning, tool calls and files. The
orchestrator surfaces a turn's text blocks in order, dropping exact repeats, and doesn't mine
tool arguments for player-facing content.

**`task_complete` stays task-agnostic.** Its only parameter is `notes`: closing notes for the
task, given only when the task asks for them.

**Unchanged:** `/meta` questions, resume (reattach or re-prime), cancel and revert, completion as a
disk fact.

## Autonomous play

`--player auto` has the `auto-player` agent play the PC with nobody at the keyboard. The engine
wraps each session and opens the next by itself, for `--sessions N` or with no limit; a session has
no turn cap unless `--turn-cap` sets one.

- **One thread for the campaign.** The player keeps one opencode session across sessions, so it
  remembers play the way a player would; compaction keeps it going. A cold start leads with its
  files and the character packet's state and knowledge.
- **Files of its own** in the project's `player/`, outside the campaign, and it can read and edit
  only those: `sheet.md`, seeded once from the PC's sheet, where it applies its own level-ups, and
  `notes.md` for its goals, leads and theories.
- **It gives no feedback.** Its feedback reached the shared store and steered the DM.
- **It is not the benchmark's player.** `player` keeps a fresh session and the generated packet per
  run ([benchmark.md](benchmark.md)).

## Combat

The tracker, commit and rollback, the per-combatant confirm gate with interjection, resume recovery
and the `advance_turn` nudge all stay — reactions make combat complicated, and the confirm gate is
how the player reacts to any enemy action. Two changes: `combat-reminder` is no longer resent each
step (the `<combat-turn>` and `<combat-reaction>` tags stay), and `check-combat` leaves play. The
archive records the tracker's committed and pending frames for every combat beat so the after-play
check can compare them with the narration.

## Wrap: reconcile

0. **Notes** arrive with the closing `task_complete`.
1. **Digest** — `log-extractor`, fresh session, reads the whole transcript and the notes and writes
   `sessions/<n>/digest.md` under the existing extraction taxonomy. `check-digest`, one correction.
2. **Feedback** — `dm` thread; code skips it when the digest has no player feedback. Distils it into
   the player-level feedback files. No check.
3. **Canon** — `dm` thread: new and changed entities, PC capabilities and level-up, the combat
   repertoire, verbatim documents. Canon lint, one correction.
4. **Arcs** — the `dm` hands each arc to a subagent, under two principles: what was played beats what
   was planned, and canon hardens once the player has seen it. The major arc re-paces its level-ups
   every pass. A close-out covers new minor arcs, the threads dashboard and the cross-arc sweep. Code
   verifies every arc is stamped `as-of: S<n>` and nudges once with any it missed; resume reads the
   same stamps.
5. **State** — `dm` thread: the ledger's subjects brought up to date (reveals by id), entity
   snapshots, `current`, `calendar`, `clocks`.
6. **`check-propagation`** — the judgment half only (did what was played land?). One correction.
7. **Commit**, then plan the next session.

## Planning

On the `dm` thread, warm from setup or reconcile. `session-plan` works without a todo list; the
focused plan skills load on demand. Inputs are the digest, the threads dashboard, the arcs and the
state — there is no assessment. Canon lint on new entities, then `check-plan` with one correction,
then a commit.

**Session 1 has a prologue.** The player remembers nothing before the first session, so its brief
also asks for `sessions/1/prologue.md`: the setting in broad strokes as the primer lays it out, then
the bridge to the opening scene — what brought the PC here and what they're after — stopping on
its threshold, so the runner sets the scene. Code nudges once if it's missing; `check-plan` reviews it with the plan.

## Substrate that carries over

Human-readable campaign files and the knowledge boundary; dice; the combat tracker; transcript
capture, completion markers, stage markers and code-owned commits; the backend, lifecycle,
frontends and cancellation; the archive.

**An interruption is resumed, not reverted.** A model call cut off by a stall, an error or the
time limit stays in its session, and the retry tells the agent to carry on: what it wrote to files
is still there, and nothing from the cut-off turn reached anyone. Each failed attempt is a `retry`
event in the archive. Only a give-up, or the player's cancel, rolls the exchange back.
