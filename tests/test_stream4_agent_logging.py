"""Stream 4：JSON 非法分支与 ReAct 停滞分支写入日志。"""

from __future__ import annotations

from unittest.mock import patch

from logos.agent.json_tools import parse_react_json
from logos.agent.react import run_react_loop
from logos.agent.tool_registry import ToolRegistry


def test_parse_react_json_decode_error_logs_warning() -> None:
    with patch("logos.agent.json_tools._log.warning") as mock_warn:
        parse_react_json('```json\n{"a":1,}\n```')
    mock_warn.assert_called()
    args = str(mock_warn.call_args)
    assert "json.loads" in args


def test_parse_react_json_non_dict_root_logs_warning() -> None:
    with patch("logos.agent.json_tools._log.warning") as mock_warn:
        parse_react_json("```json\n[1]\n```")
    mock_warn.assert_called()
    assert "list" in str(mock_warn.call_args)


def test_parse_react_json_final_answer_nested_object_serialized() -> None:
    """LLM 把 final_answer 写成嵌套对象时，应序列化为字符串而非判为非法。"""
    step = parse_react_json(
        '{"thought": "x", "final_answer": {"title": "t", "steps": ["a", "b"]}}'
    )
    assert step.final_answer is not None
    assert '"title"' in step.final_answer
    assert '"steps"' in step.final_answer
    assert step.action_name is None


def test_parse_react_json_final_answer_string_unchanged() -> None:
    step = parse_react_json(
        '{"thought": "x", "final_answer": "{\\"title\\": \\"t\\", \\"steps\\": [\\"a\\"]}"}'
    )
    assert step.final_answer == '{"title": "t", "steps": ["a"]}'


def test_run_react_loop_logs_on_format_nudge() -> None:
    class _NoiseLLM:
        def complete(self, messages, *, json_mode: bool = False) -> str:
            return "not json at all"

        def stream_completion(self, messages, *, json_mode: bool = False):
            yield self.complete(messages, json_mode=json_mode)

    reg = ToolRegistry()
    with patch("logos.agent.react._log.info") as mock_info:
        run_react_loop(_NoiseLLM(), reg, "task", max_steps=6)
    assert mock_info.call_count >= 1
    joined = " ".join(str(c) for c in mock_info.call_args_list)
    assert "final_answer" in joined or "ReAct" in joined


def test_run_react_loop_logs_on_exhausted_nudge() -> None:
    class _NoiseLLM:
        def complete(self, messages, *, json_mode: bool = False) -> str:
            return "still not json"

        def stream_completion(self, messages, *, json_mode: bool = False):
            yield self.complete(messages, json_mode=json_mode)

    reg = ToolRegistry()
    with patch("logos.agent.react._log.warning") as mock_warn:
        res = run_react_loop(_NoiseLLM(), reg, "x", max_steps=8)
    assert "已停止" in res.answer
    mock_warn.assert_called()
    assert "JSON" in str(mock_warn.call_args)
