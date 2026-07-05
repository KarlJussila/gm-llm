"""gm-llm — an LLM game master for solo, long-form D&D campaigns, over opencode.

This package is the installable *tool*: the `gm-llm` command (launch the TUI, scaffold
a project, check the environment). The engine lives in `gm_llm.orchestrator`, the UI
in `gm_llm.tui`, and the opencode assets (agents, skills, plugin) ship as package data
and are copied into a project by `gm-llm init`.
"""

__version__ = "0.1.1"
