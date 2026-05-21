"""Dialogue paradigm executor: natural-language LLM, no ReAct JSON protocol."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb
from logos.agent.prompt_echo import format_messages_for_prompt_echo
from logos.agent.tool_registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class DialogueResult:
    answer: str
    messages: list[ChatMessage]


@dataclass(frozen=True, slots=True)
class DialogueStreamText:
    """流式正文片段（映射为 SSE ``delta``）。"""

    text: str


@dataclass(frozen=True, slots=True)
class DialogueStreamDone:
    result: DialogueResult


def iter_dialogue_task(
    llm: LLMClient,
    skill_id: str,
    user_text: str,
    *,
    extra_system: str | None = None,
    history: list[ChatMessage] | None = None,
    registry: ToolRegistry | None = None,
    task_input: dict[str, Any] | None = None,
    stream_assistant: bool = True,
    prompt_echo: bool = False,
) -> Iterator[DialogueStreamText | DialogueStreamDone]:
    """对话范式：``json_mode=false``，流式自然语言输出。"""
    messages = cb.seed_dialogue_messages(
        skill_id,
        history or [],
        user_text,
        extra_system=extra_system,
        registry=registry,
        task_input=task_input,
    )
    if prompt_echo:
        echo_text = format_messages_for_prompt_echo(messages)
        yield DialogueStreamDone(DialogueResult(answer=echo_text, messages=messages))
        return

    answer = ""
    if stream_assistant:
        for piece in llm.stream_completion(messages, json_mode=False):
            if piece:
                answer += piece
                yield DialogueStreamText(text=piece)
    else:
        answer = llm.complete(messages, json_mode=False)

    yield DialogueStreamDone(DialogueResult(answer=answer, messages=messages))
