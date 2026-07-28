# design/ — routing

Plan-of-record and archive docs. `tools/lint_docs.py` check 1 fails if a doc here is not
linked from this table, so add the row when you add the doc.

| Doc | What it is |
|---|---|
| [findings.md](findings.md) | The append-only round archive — one Part per round. Point-in-time; read it for *why* a call was made. |
| [open-questions.md](open-questions.md) | The live backlog of unresolved decisions and known gaps. Resolved items are deleted, not tombstoned. |
| [frontends.md](frontends.md) | Plan of record for frontend/mode modularity — watching autoplay and bench runs in the TUI. |

Plan-of-record docs that predate this directory live at the repo root and are pointed at
from `ROADMAP.md`: `BENCHMARK.md` (the benchmark workstream), `COMBAT.md` (combat),
`PLAN.md` (packaging / native Windows), `SPEC.md` (what the system is).
