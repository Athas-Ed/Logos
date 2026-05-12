"""ReAct loop helpers (single-tool step per iteration)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb, json_tools
from logos.agent.prompt_echo import format_messages_for_prompt_echo
from logos.agent.tool_registry import ToolRegistry

_log = logging.getLogger("logos.agent.react")


@dataclass(frozen=True, slots=True)
class ReActResult:
    answer: str
    steps: int
    messages: list[ChatMessage]


@dataclass(frozen=True, slots=True)
class ReActStreamReasoning:
    """单轮助手输出在流式生成中的一段（多为 JSON 模式下的 token）。"""

    text: str


@dataclass(frozen=True, slots=True)
class ReActStreamDone:
    """ReAct 结束（成功 final_answer、工具循环中止或步数上限）。"""

    result: ReActResult


def iter_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
    history: list[ChatMessage] | None = None,
    stream_assistant: bool = True,
    prompt_echo: bool = False,
) -> Iterator[ReActStreamReasoning | ReActStreamDone]:
    """与 :func:`run_react_loop` 相同语义；若 *stream_assistant* 则每轮助手输出以流式片段产出。"""
    messages = cb.seed_messages_with_history(
        registry,
        history or [],
        user_text,
        extra_system=extra_system,
    )
    if prompt_echo:
        echo_text = format_messages_for_prompt_echo(messages)
        yield ReActStreamDone(
            ReActResult(answer=echo_text, steps=0, messages=messages)
        )
        return
    steps = 0
    nudge_budget = 2

    while steps < max_steps:
        steps += 1
        assistant_text = ""
        if stream_assistant:
            for piece in llm.stream_completion(messages, json_mode=json_mode):
                if piece:
                    assistant_text += piece
                    yield ReActStreamReasoning(text=piece)
        else:
            assistant_text = llm.complete(messages, json_mode=json_mode)

        cb.append_assistant(messages, assistant_text)
        step = json_tools.parse_react_json(assistant_text)

        if step.final_answer is not None:
            yield ReActStreamDone(
                ReActResult(answer=step.final_answer, steps=steps, messages=messages)
            )
            return

        if step.action_name:
            obs = registry.execute(step.action_name, step.action_arguments)
            cb.append_observation(messages, obs)
            continue

        if nudge_budget <= 0:
            _log.warning(
                "ReAct 在 %d 步内仍无法得到合法 JSON 步骤（已无重试预算），停止循环。",
                steps,
            )
            yield ReActStreamDone(
                ReActResult(
                    answer="已停止：连续多轮无法解析为有效的 JSON 工具步骤。",
                    steps=steps,
                    messages=messages,
                )
            )
            return
        nudge_budget -= 1
        detail = "缺少 final_answer 与合法 action"
        if step.thought:
            detail += f"；thought 摘要：{step.thought[:200]}"
        _log.info("ReAct 输出不完整，追加格式提示：%s", detail[:300])
        cb.append_format_nudge(messages, detail)

    _log.warning("ReAct 达到最大步数上限（%d），仍未结束。", max_steps)
    yield ReActStreamDone(
        ReActResult(
            answer="已停止：达到 ReAct 最大步数上限。",
            steps=steps,
            messages=messages,
        )
    )


def run_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
    history: list[ChatMessage] | None = None,
    prompt_echo: bool = False,
) -> ReActResult:
    """Thought → (optional) tool → observation, until final_answer or cap（非流式）。"""
    final: ReActResult | None = None
    for item in iter_react_loop(
        llm,
        registry,
        user_text,
        max_steps=max_steps,
        extra_system=extra_system,
        json_mode=json_mode,
        history=history,
        stream_assistant=False,
        prompt_echo=prompt_echo,
    ):
        if isinstance(item, ReActStreamDone):
            final = item.result
    if final is None:
        msg = "iter_react_loop 未产生结束状态"
        raise RuntimeError(msg)
    return final
