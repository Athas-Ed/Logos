"""Minimal context builder: system instructions + rolling chat for ReAct."""

from __future__ import annotations

from logos.ports.llm import ChatMessage

from logos.agent.tool_registry import ToolRegistry


def build_react_system_message(registry: ToolRegistry) -> str:
    tools = registry.tools_prompt_section()
    return (
        "你是 Agent 的推理模块。每一轮必须只回复**一个** JSON 对象（键名保持英文，与下述示例一致），"
        "不要在该 JSON 外再包一层说明文字：\n"
        "1）若无需工具即可作答："
        '{"thought": "…", "final_answer": "…"}\n'
        "2）若需调用工具："
        '{"thought": "…", "action": {"name": "工具名", "arguments": { … 参数 … }}}\n'
        "每轮最多一次工具调用；name 必须与下方目录中的工具名完全一致。\n"
        "工具目录（JSON 数组）：\n"
        f"{tools}\n"
        "说明：thought / final_answer / action / name / arguments 等字段名请勿改写或翻译。"
    )


def seed_messages(
    registry: ToolRegistry,
    user_text: str,
    *,
    extra_system: str | None = None,
) -> list[ChatMessage]:
    """Initial messages for a ReAct session."""
    return seed_messages_with_history(
        registry,
        [],
        user_text,
        extra_system=extra_system,
    )


def seed_messages_with_history(
    registry: ToolRegistry,
    history: list[ChatMessage],
    user_text: str,
    *,
    extra_system: str | None = None,
) -> list[ChatMessage]:
    """system + 历史 user/assistant 轮次 + 当前 user（*history* 不含 system）。"""
    system = build_react_system_message(registry)
    if extra_system:
        system = system + "\n\n" + extra_system.strip()
    out: list[ChatMessage] = [ChatMessage(role="system", content=system)]
    out.extend(history)
    out.append(ChatMessage(role="user", content=user_text.strip()))
    return out


def append_assistant(messages: list[ChatMessage], content: str) -> None:
    messages.append(ChatMessage(role="assistant", content=content))


def append_observation(messages: list[ChatMessage], observation: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content="工具观测结果：\n" + observation.strip(),
        )
    )


def append_format_nudge(messages: list[ChatMessage], detail: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content=(
                "你上一轮输出不是符合约定的单个 JSON 对象。请重新回复，且**仅包含**一个 JSON 对象（键名仍为英文）。"
                f"\n说明：{detail}"
            ),
        )
    )
