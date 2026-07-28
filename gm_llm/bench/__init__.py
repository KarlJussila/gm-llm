"""
The benchmark harness (design/benchmark.md) — not shipped in the wheel.

gm-llm doubles as a tiered scaffolding benchmark: an autoplayer runs a full session
against a frozen fixture campaign and the gate's verdicts, captured in the score-event
archive (`gm_llm.orchestrator.archive`), become the score. This package is the
developer-side driver for that — `bench run` prepares condition-stamped run dirs,
plays them to a natural close (or a hard turn cap), and optionally reconciles, leaving
one archive per run for the later grading/report passes (B2).

It lives under `gm_llm/` for clean imports but is excluded from the wheel exactly like
`dev/` — pyproject's `packages` list is explicit and omits it. Nothing the shipped
product does depends on anything here.
"""
