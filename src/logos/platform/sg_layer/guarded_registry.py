"""工具白名单，与 :class:`~logos.agent.tool_registry.ToolRegistry` 组合使用。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from logos.agent.tool_registry import ToolRegistry

# V0.1 契约中的最小工具集（与 DEVPLAN / SPEC 对齐；未实现的工具可稍后注册）。
V01_SG_TOOL_WHITELIST: frozenset[str] = frozenset(
    {
        "retrieve",
        "read_ksfs",
        "list_ksfs",
        "write_draft",
        "list_drafts",
        "read_draft",
        "promote_draft",
    },
)

# 与 ``skills/example-stdio-mcp`` 中 MCP 工具名对齐；仅在使用 MCP 桥接时加入 ``extra_allowed_tools``。
V01_EXAMPLE_MCP_TOOL_NAMES: frozenset[str] = frozenset({"echo_write_draft"})


class GuardedToolRegistry(ToolRegistry):
    """在注册与执行阶段强制执行工具白名单。工具输出长度由 CB budget 在写入消息时控制。"""

    __slots__ = ("_allowed",)

    def __init__(
        self,
        *,
        allowed_names: frozenset[str] | None = None,
    ) -> None:
        super().__init__()
        self._allowed: frozenset[str] = (
            allowed_names if allowed_names is not None else V01_SG_TOOL_WHITELIST
        )

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
        return super().execute(name, arguments)
