#!/usr/bin/env python3
"""Standalone check for the campaign's model (`gm-llm.yaml`'s `model` / `variant`, and the
`--model` / `--variant` flags over them): every agent in the project is re-pinned through
opencode's `agent` config, which reaches the subagents opencode starts itself. No pytest, no
opencode — run me directly."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator.backend import Backend, agent_overrides  # noqa: E402


def _project(root: Path) -> Path:
    agents = root / ".opencode" / "agent"
    agents.mkdir(parents=True)
    for name in ("dm", "author"):
        (agents / f"{name}.md").write_text(
            f"---\ndescription: {name}\nmode: primary\nmodel: openai/gpt-6-luna\n"
            "variant: xhigh\n---\nBody.\n", encoding="utf-8")
    (agents / "notes.md").write_text("no frontmatter\n", encoding="utf-8")
    return root


def main(root: Path) -> None:
    project = _project(root)
    assert agent_overrides(project) == {}, "no flags, no overrides"

    glm = agent_overrides(project, "opencode/glm-5.3-flash-free")
    assert glm == {name: {"model": "opencode/glm-5.3-flash-free", "variant": ""}
                   for name in ("author", "dm")}, \
        "a new model drops the pinned variant (empty clears it; a null would void the entry)"

    assert agent_overrides(project, "opencode/glm-5.3-flash-free", "high")["dm"]["variant"] == "high"
    assert agent_overrides(project, variant="low")["author"] == \
        {"model": "openai/gpt-6-luna", "variant": "low"}, \
        "a variant alone keeps each agent's model — opencode needs the model named"

    # gm-llm.yaml sets the campaign's model; the flags win over it, a field at a time, and a
    # model from either brings its own variant.
    (project / "gm-llm.yaml").write_text("model: opencode/deepseek-v4.1-flash-free\nvariant: high\n",
                                         encoding="utf-8")
    assert agent_overrides(project)["dm"] == \
        {"model": "opencode/deepseek-v4.1-flash-free", "variant": "high"}
    assert agent_overrides(project, "opencode/glm-5.3-flash-free")["dm"] == \
        {"model": "opencode/glm-5.3-flash-free", "variant": ""}, "the file's variant was for its model"
    assert agent_overrides(project, variant="low")["dm"] == \
        {"model": "opencode/deepseek-v4.1-flash-free", "variant": "low"}
    (project / "gm-llm.yaml").write_text("variant: low\n", encoding="utf-8")
    assert agent_overrides(project)["author"] == {"model": "openai/gpt-6-luna", "variant": "low"}
    (project / "gm-llm.yaml").write_text("model: glm-5.3\n", encoding="utf-8")
    try:
        agent_overrides(project)
        raise AssertionError("a model without its provider is refused")
    except ValueError:
        pass
    (project / "gm-llm.yaml").unlink()

    config = Backend(str(project), agents=glm).server_config()
    assert config["agent"]["dm"]["model"] == "opencode/glm-5.3-flash-free"
    assert config["compaction"] == {"auto": False}, "the server's own config stays"
    assert "agent" not in Backend(str(project)).server_config()
    print("OK — the campaign's model reaches every agent through the server config; flags win.")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="gm-models-") as temp:
        main(Path(temp))
