"""Prompt 回显（不调用 LLM，用于检视 CB 拼装结果）。"""

from __future__ import annotations

from logos.ports.llm import ChatMessage


def format_messages_for_prompt_echo(messages: list[ChatMessage]) -> str:
    """将本轮将送往模型的 messages 格式化为可读文本。"""
    lines: list[str] = [
        "【Prompt 回显模式】未调用 LLM。以下为本轮请求将发送的 messages（含 system / user / assistant）：",
        "",
    ]
    for i, m in enumerate(messages):
        lines.append(f"--- [{i}] role={m.role} ---")
        lines.append(m.content)
        lines.append("")
    return "\n".join(lines).rstrip()
