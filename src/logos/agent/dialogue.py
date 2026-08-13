"""Dialogue paradigm executor: natural-language LLM, no ReAct JSON protocol."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb
from logos.agent.tool_registry import ToolRegistry

_log = logging.getLogger("logos.agent.dialogue")


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


def _retrieve_ksfs_context(
    user_text: str,
    registry: ToolRegistry,
    max_reads: int = 2,
) -> str | None:
    """自动检索 KSFS 知识并注入上下文。

    在 dialogue 范式下，若工具注册表包含 ``retrieve`` / ``read_ksfs``，
    在调用 LLM 前自动查询与用户输入相关的已有设定，返回格式化上下文文本。
    返回 ``None`` 表示无相关结果或工具不可用。
    """
    if "retrieve" not in registry.names():
        return None

    try:
        result_json = registry.execute("retrieve", {"text": user_text, "top_k": 4})
    except Exception:
        _log.exception("dialogue auto-retrieve 调用失败")
        return None

    try:
        results = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(results, list) or not results:
        return None

    context_parts: list[str] = []
    for entry in results[:max_reads]:
        path = entry.get("path", "")
        if not path:
            continue
        try:
            content = registry.execute("read_ksfs", {"path": path})
        except Exception:
            continue
        if not content or content.startswith("error:"):
            continue
        # Trim very long content to ~2000 chars to keep prompt size manageable
        snippet = content[:2000]
        if len(content) > 2000:
            snippet += "\n\n…（以下省略）"
        context_parts.append(f"### {path}\n\n{snippet}")

    if not context_parts:
        return None

    return (
        "【KSFS 知识上下文】\n\n"
        + "\n\n---\n\n".join(context_parts)
        + "\n\n请基于以上已有设定进行回答与启发。"
    )


def iter_dialogue_task(
    llm: LLMClient,
    skill_id: str,
    user_text: str,
    *,
    extra_system: str | None = None,
    history: list[ChatMessage] | None = None,
    registry: ToolRegistry | None = None,
    stream_assistant: bool = True,
) -> Iterator[DialogueStreamText | DialogueStreamDone]:
    """对话范式：``json_mode=false``，流式自然语言输出。"""
    # 自动检索 KSFS 上下文注入
    ksfs_ctx = None
    if registry:
        ksfs_ctx = _retrieve_ksfs_context(user_text, registry)
    if ksfs_ctx is not None:
        extra_system = (extra_system or "") + "\n\n" + ksfs_ctx

    messages = cb.seed_dialogue_messages(
        skill_id,
        history or [],
        user_text,
        extra_system=extra_system,
        registry=registry,
    )
    answer = ""
    if stream_assistant:
        for piece in llm.stream_completion(messages, json_mode=False):
            if piece:
                answer += piece
                yield DialogueStreamText(text=piece)
    else:
        answer = llm.complete(messages, json_mode=False)

    yield DialogueStreamDone(DialogueResult(answer=answer, messages=messages))
