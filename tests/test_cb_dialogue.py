"""PR-2：dialogue CB 拼装不含 ReAct JSON 条令。"""

from __future__ import annotations

from logos.agent.cb import (
    REACT_JSON_MANDATE_MARKERS,
    build_dialogue_system_message,
    compose_prompt,
    load_prompt_fragment,
)
from logos.agent.tool_registry import ToolRegistry


def test_lint_zh_fragment_loads() -> None:
    text = load_prompt_fragment("skills/lint_zh.md")
    assert "语病" in text


def test_dialogue_system_excludes_react_json_mandate() -> None:
    system = build_dialogue_system_message("lint_zh")
    for marker in REACT_JSON_MANDATE_MARKERS:
        assert marker not in system


def test_compose_prompt_lint_zh_dialogue() -> None:
    system = compose_prompt("dialogue", "p2", "lint_zh")
    assert "lint_zh" in system or "语病" in system
    assert REACT_JSON_MANDATE_MARKERS[0] not in system


def test_compose_prompt_react_includes_mandate() -> None:
    reg = ToolRegistry()
    system = compose_prompt("react", "p2", "retrieve_qa", reg)
    assert REACT_JSON_MANDATE_MARKERS[0] in system
