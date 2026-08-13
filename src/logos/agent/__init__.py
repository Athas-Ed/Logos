"""决策层：TaskSession 统一入口、ReAct 循环、JSON 工具解析、最小 CB/PR、工具注册表 — Stream 4。"""

from logos.agent.cb import (
    REACT_JSON_MANDATE_MARKERS,
    append_assistant,
    append_format_nudge,
    append_observation,
    build_dialogue_system_message,
    build_react_system_message,
    compose_prompt,
    seed_dialogue_messages,
    seed_messages,
)
from logos.agent.dialogue import (
    DialogueResult,
    DialogueStreamDone,
    DialogueStreamText,
    iter_dialogue_task,
)
from logos.agent.json_tools import ParsedStep, parse_react_json
from logos.agent.pr import select_paradigm
from logos.agent.react import (
    ReActResult,
    ReActStreamDone,
    ReActStreamReasoning,
    ReActStreamToolTrace,
    iter_react_loop,
    run_react_loop,
)
from logos.agent.task import (
    TaskCitations,
    TaskDone,
    TaskEvent,
    TaskPipelineStep,
    TaskPipelineWarning,
    TaskReasoning,
    TaskSession,
    TaskText,
    TaskToolTrace,
    merge_task_input_into_user,
)
from logos.agent.tool_registry import RegisteredTool, ToolRegistry

__all__ = [
    "DialogueResult",
    "DialogueStreamDone",
    "DialogueStreamText",
    "ParsedStep",
    "REACT_JSON_MANDATE_MARKERS",
    "ReActResult",
    "ReActStreamDone",
    "ReActStreamReasoning",
    "ReActStreamToolTrace",
    "RegisteredTool",
    "TaskCitations",
    "TaskDone",
    "TaskEvent",
    "TaskPipelineStep",
    "TaskPipelineWarning",
    "TaskReasoning",
    "TaskSession",
    "TaskText",
    "TaskToolTrace",
    "ToolRegistry",
    "append_assistant",
    "append_format_nudge",
    "append_observation",
    "build_dialogue_system_message",
    "build_react_system_message",
    "compose_prompt",
    "iter_dialogue_task",
    "merge_task_input_into_user",
    "parse_react_json",
    "iter_react_loop",
    "run_react_loop",
    "seed_dialogue_messages",
    "seed_messages",
    "select_paradigm",
]
