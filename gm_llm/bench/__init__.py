"""
The benchmark harness (design/benchmark.md) — not shipped in the wheel.

gm-llm doubles as a tiered scaffolding benchmark: an autoplayer runs a full session
against a frozen fixture campaign, and the mistakes found in its archive
(`gm_llm.orchestrator.archive`) become the score. `bench run` plays condition-stamped
runs, `bench check` finds each turn's mistakes after play, `bench grade` confirms or
rejects and grades them, and `bench report` rolls a batch up.

It lives under `gm_llm/` for clean imports but is excluded from the wheel exactly like
`dev/` — pyproject's `packages` list is explicit and omits it. Nothing the shipped
product does depends on anything here.
"""
