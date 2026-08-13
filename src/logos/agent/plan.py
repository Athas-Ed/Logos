"""Plan paradigm Phase A: single LLM call producing a human-readable plan (no Phase B execution)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb
from logos.agent.dialogue import DialogueResult, DialogueStreamDone, DialogueStreamText


@dataclass(frozen=True, slots=True)
class PlanResult:
    """Phase A 产出：计划正文（JSON 或 Markdown）。"""

    plan_text: str
    messages: list[ChatMessage]

    @property
    def answer(self) -> str:
        """与 :class:`DialogueResult` 对齐，供 Shell / SSE 复用。"""
        return self.plan_text


def iter_plan_phase_a(
    llm: LLMClient,
    skill_id: str,
    user_text: str,
    *,
    extra_system: str | None = None,
    history: list[ChatMessage] | None = None,
    stream_assistant: bool = True,
) -> Iterator[DialogueStreamText | DialogueStreamDone]:
    """Plan Phase A：``json_mode=true`` 一次生成计划，流式映射为 SSE ``delta``。"""
    messages = cb.seed_plan_messages(
        skill_id,
        history or [],
        user_text,
        extra_system=extra_system,
    )

    plan_text = ""
    if stream_assistant:
        for piece in llm.stream_completion(messages, json_mode=True):
            if piece:
                plan_text += piece
                yield DialogueStreamText(text=piece)
    else:
        plan_text = llm.complete(messages, json_mode=True)

    result = DialogueResult(answer=plan_text.strip(), messages=messages)
    yield DialogueStreamDone(result)
