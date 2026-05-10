"""决策层：Agent Shell、ReAct 循环、JSON 工具解析、最小 CB/PR、工具注册表 — Stream 4。"""

from logos.agent.cb import (
    append_assistant,
    append_format_nudge,
    append_observation,
    build_react_system_message,
    seed_messages,
)
from logos.agent.json_tools import ParsedStep, parse_react_json
from logos.agent.pr import select_paradigm
from logos.agent.react import (
    ReActResult,
    ReActStreamDone,
    ReActStreamReasoning,
    iter_react_loop,
    run_react_loop,
)
from logos.agent.shell import AgentShell
from logos.agent.tool_registry import RegisteredTool, ToolRegistry

__all__ = [
    "AgentShell",
    "ParsedStep",
    "ReActResult",
    "ReActStreamDone",
    "ReActStreamReasoning",
    "RegisteredTool",
    "ToolRegistry",
    "append_assistant",
    "append_format_nudge",
    "append_observation",
    "build_react_system_message",
    "parse_react_json",
    "iter_react_loop",
    "run_react_loop",
    "seed_messages",
    "select_paradigm",
]
