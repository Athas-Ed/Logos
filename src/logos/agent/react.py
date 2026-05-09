"""ReAct loop helpers (single-tool step per iteration)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb, json_tools
from logos.agent.tool_registry import ToolRegistry

_log = logging.getLogger("logos.agent.react")


@dataclass(frozen=True, slots=True)
class ReActResult:
    answer: str
    steps: int
    messages: list[ChatMessage]


def run_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
) -> ReActResult:
    """Thought → (optional) tool → observation, until final_answer or cap."""
    messages = cb.seed_messages(registry, user_text, extra_system=extra_system)
    steps = 0
    nudge_budget = 2

    while steps < max_steps:
        steps += 1
        assistant_text = llm.complete(messages, json_mode=json_mode)
        cb.append_assistant(messages, assistant_text)
        step = json_tools.parse_react_json(assistant_text)

        if step.final_answer is not None:
            return ReActResult(answer=step.final_answer, steps=steps, messages=messages)

        if step.action_name:
            obs = registry.execute(step.action_name, step.action_arguments)
            cb.append_observation(messages, obs)
            continue

        if nudge_budget <= 0:
            _log.warning(
                "ReAct 在 %d 步内仍无法得到合法 JSON 步骤（已无重试预算），停止循环。",
                steps,
            )
            return ReActResult(
                answer="已停止：连续多轮无法解析为有效的 JSON 工具步骤。",
                steps=steps,
                messages=messages,
            )
        nudge_budget -= 1
        detail = "缺少 final_answer 与合法 action"
        if step.thought:
            detail += f"；thought 摘要：{step.thought[:200]}"
        _log.info("ReAct 输出不完整，追加格式提示：%s", detail[:300])
        cb.append_format_nudge(messages, detail)

    _log.warning("ReAct 达到最大步数上限（%d），仍未结束。", max_steps)
    return ReActResult(
        answer="已停止：达到 ReAct 最大步数上限。",
        steps=steps,
        messages=messages,
    )
