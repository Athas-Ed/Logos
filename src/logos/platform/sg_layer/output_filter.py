"""工具返回内容的简单治理：超长输出截断，避免观测与上下文爆炸。"""

from __future__ import annotations


def filter_tool_output(text: str, max_chars: int) -> str:
    """若 *text* 超过 *max_chars*，截断并追加提示后缀。"""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    suffix = "\n…[输出已按 S&G 策略截断]…"
    budget = max_chars - len(suffix)
    if budget <= 0:
        return suffix.strip()
    return text[:budget] + suffix
