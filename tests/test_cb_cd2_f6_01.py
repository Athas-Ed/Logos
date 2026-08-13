"""F6-01 CD-2：react base 与 operating mode 从 resources/prompts 加载。"""

from __future__ import annotations

from unittest.mock import patch

from logos.agent.cb import (
    REACT_JSON_MANDATE_MARKERS,
    build_react_system_message,
    load_operating_mode_suffix,
    load_prompt_fragment,
)
from logos.agent.tool_registry import ToolRegistry


def test_react_base_loads_from_resource() -> None:
    base = load_prompt_fragment("paradigms/react/base.md")
    assert "推理模块" in base
    assert "{{TOOLS_JSON}}" in base
    reg = ToolRegistry()
    system = build_react_system_message(reg)
    for marker in REACT_JSON_MANDATE_MARKERS:
        assert marker in system
    assert "{{TOOLS_JSON}}" not in system


def test_react_system_changes_when_base_md_changes() -> None:
    custom = "【CD-2 探针】自定义 ReAct 条令。\n{{TOOLS_JSON}}"
    reg = ToolRegistry()

    def fake_load(rel: str) -> str:
        if rel == "paradigms/react/base.md":
            return custom
        return load_prompt_fragment(rel)

    with patch("logos.agent.cb.load_prompt_fragment", side_effect=fake_load):
        system = build_react_system_message(reg)
    assert "【CD-2 探针】" in system
    assert REACT_JSON_MANDATE_MARKERS[0] not in system


def test_operating_mode_suffix_from_modes_md() -> None:
    author = load_operating_mode_suffix("author")
    # screenwriter 参数（director 等）未开发：缺失片段回退 author 内容
    screen = load_operating_mode_suffix("screenwriter")
    assert "作者" in author and "author" in author
    assert "作者" in screen and "author" in screen
    assert screen == author


def test_operating_mode_suffix_changes_when_md_changes() -> None:
    probe = "【CD-2 探针】运行模式后缀"

    def fake_load(rel: str) -> str:
        if rel == "modes/author.md":
            return probe
        return load_prompt_fragment(rel)

    with patch("logos.agent.cb.load_prompt_fragment", side_effect=fake_load):
        assert load_operating_mode_suffix("author") == probe
