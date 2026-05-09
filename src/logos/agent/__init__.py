"""Decision layer: Agent Shell, ReAct loop, JSON tool parsing, minimal CB/PR, tool registry."""

from logos.agent.cb import (
    append_assistant,
    append_format_nudge,
    append_observation,
    build_react_system_message,
    seed_messages,
)
from logos.agent.json_tools import ParsedStep, parse_react_json
from logos.agent.pr import select_paradigm
from logos.agent.react import ReActResult, run_react_loop
from logos.agent.shell import AgentShell
from logos.agent.tool_registry import RegisteredTool, ToolRegistry

__all__ = [
    "AgentShell",
    "ParsedStep",
    "ReActResult",
    "RegisteredTool",
    "ToolRegistry",
    "append_assistant",
    "append_format_nudge",
    "append_observation",
    "build_react_system_message",
    "parse_react_json",
    "run_react_loop",
    "seed_messages",
    "select_paradigm",
]
