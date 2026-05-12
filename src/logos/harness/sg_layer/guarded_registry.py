"""工具白名单 + 输出过滤，与 :class:`~logos.agent.tool_registry.ToolRegistry` 组合使用。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from logos.agent.tool_registry import ToolRegistry

from .output_filter import filter_tool_output

# V0.1 契约中的最小工具集（与 DEVPLAN / SPEC 对齐；未实现的工具可稍后注册）。
V01_SG_TOOL_WHITELIST: frozenset[str] = frozenset(
    {"retrieve", "read_ksfs", "list_ksfs", "write_draft"},
)


class GuardedToolRegistry(ToolRegistry):
    """在注册与执行阶段强制执行工具白名单，并对工具输出做长度限制。"""

    __slots__ = ("_allowed", "_max_output_chars")

    def __init__(
        self,
        *,
        allowed_names: frozenset[str] | None = None,
        max_output_chars: int = 100_000,
    ) -> None:
        super().__init__()
        self._allowed: frozenset[str] = (
            allowed_names if allowed_names is not None else V01_SG_TOOL_WHITELIST
        )
        self._max_output_chars = max_output_chars

    def register(
        self,
        name: str,
        *,
        description: str,
        parameters: dict[str, Any],
        handler: Any,
    ) -> None:
        if name not in self._allowed:
            msg = f"工具 {name!r} 不在 S&G 白名单中，禁止注册"
            raise ValueError(msg)
        super().register(
            name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def execute(self, name: str, arguments: Mapping[str, Any] | None) -> str:
        if name not in self._allowed:
            return f"error: 工具 {name!r} 被 S&G 策略拒绝（不在白名单）"
        raw = super().execute(name, arguments)
        return filter_tool_output(raw, self._max_output_chars)
