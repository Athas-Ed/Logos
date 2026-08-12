"""S&G 输出治理：工具返回内容超长截断，避免观测写入 LLM 上下文时膨胀。

接线：由 ``GuardedToolRegistry.execute`` 在工具结果返回后统一应用（内置与 MCP 工具一致）；
上限来自配置 ``agent.react.max_tool_observation_chars``（0/None 表示不截断）。
与生成质量路线项 H3「CB 预算与裁剪」配套。
"""

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
