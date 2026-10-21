# Handoff — after luna 3 and the opencode 2.x port (2026-10-20)

Temporary: delete this file once luna 4 lands. The plan is `ROADMAP.md`; the design is
`design/luna.md`. Run things through `.venv/bin/python` (see `CLAUDE.md`). The tree is clean and the
suite is green.

## Done this session

- **luna 2 — live play and combat** (`4925973`). The in-play gate (`Gate.check`, `GateResult`)
  and the briefs only it used are deleted; every agent is pinned to `openai/gpt-6-luna` +
  `variant: xhigh`.
- **luna 3 — reconcile and planning** (`6fc3bc4`). The commit message has the list. Worth knowing:
  - Setup now stamps state `as-of: S0`, not `S1`. `as-of: S<n>` means "as of the end of session
    n", and with `S1` at setup the arc coverage check couldn't tell whether session 1's arcs had
    been reconciled. `design/luna.md` § Setup is updated. Karl hasn't confirmed this yet.
  - `log-extract` is folded into `agent/log-extractor.md`.
  - The new `agent/author.md` subagent is the only agent `dm` may call through `task`.
  - Every gate archives the diff its correction made (`phase.correct_once`).
- **The opencode 2.x port** (`2a8ddb8`, `31bb3fe`, `f423432`). opencode 2.0 dropped the v1 API.
  Needs opencode ≥ 2.1, which `gm-llm doctor` checks.
  - `Backend` uses the v2 API: basic auth, prompts into the session inbox, wait for idle, read the
    turn back from the session's messages.
  - Two v2 traps are handled in `backend.py`, so don't undo them:
    - Switching a session's agent doesn't switch its model, so `_use_agent` sets the agent's pinned
      model too. Without that, agents silently run on the server's default free model.
    - A fresh server answers before it has loaded the project's agents, so `_agent_model` waits
      for a 404 to clear.
  - The plugins are native v2 plugins: a default `{ id, setup }` export that registers JSON-Schema
    tools via `ctx.tool.transform`, with `options: { codemode: false }`. Without that option, tools
    are reachable only from code mode and the orchestrator can't read `task_complete` /
    `report_findings`.
  - The plugins import nothing, so the npm install step is gone. `gm-llm update` removes the old
    `package.json` / `node_modules`.

## Live evidence so far

One Hollowfell play-only run on Luna through the ported stack:
`bench-out/luna2/run-20261021T014918Z-1961/` (archive under `.opencode/logs/`, gitignored).

- 24 turns, wrapped naturally. One `task_complete` carried the closing narration and the notes;
  no close nudge.
- `sessions/3/notes.md` is good.
- Context went from 39k to 72k tokens (of 272k).
- The DM loaded skills 3 times and **never read a campaign file mid-session**. That's not a
  permissions problem: a direct test showed the runner reads files fine. It's Luna working from the
  prepared context. Keep an eye on it in luna 6 before writing any guardrail; under the
  `refine-prompts` rule a guardrail needs a run that shows the failure.

To run one: `.venv/bin/gm-llm bench run --play-only --out bench-out/<name>`. Add `--stream` to watch
the model live.

## Next

1. **luna 4 — setup and player-level feedback** (ROADMAP has the scope; `design/luna.md` § Setup and
   principles 9–10 have the design). Feedback is still under `campaign/feedback/`, and the
   `curate-feedback-brief` and `feedback-curation` skill write there; luna 4 moves it to the
   player-level store. The `subagents: sequential | parallel` setting becomes one sentence in
   `apply-arcs-brief.md`, which currently says "one at a time".
2. luna 5 sweep. Known leftovers: the `check-turn`/`check-conduct`/`check-combat` skills,
   `campaign-setup`, the `narrative-checker` prompt's todo protocol, and the stale architecture in
   `README.md` and `design/README.md`.
3. luna 6 can start any time now that live runs work.

## Open, outside the repo

- Karl's global `~/.config/opencode/plugin/task-signal.ts` and `plugins/dice-roller.ts` are v1
  plugins and fail to load under opencode 2.x. They're harmless to gm-llm, but broken for his own
  use.
- The user's global MCP servers and skills load into campaign sessions as well. No code-mode
  catalog showed up in the runner's session (its `'*': deny` permissions likely keep it out), but
  for benchmark comparability it may be worth isolating campaign servers from the global config
  later.
- Native Windows, including the new `@opencode/cli` install, is untested (ROADMAP packaging 1).
