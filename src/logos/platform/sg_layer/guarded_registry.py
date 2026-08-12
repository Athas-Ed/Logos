"""工具白名单，与 :class:`~logos.agent.tool_registry.ToolRegistry` 组合使用。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from logos.agent.tool_registry import ToolRegistry
from logos.platform.sg_layer.output_filter import filter_tool_output

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
        "kg_query",
    },
)

# 与 ``skills/example-stdio-mcp`` 中 MCP 工具名对齐；仅在使用 MCP 桥接时加入 ``extra_allowed_tools``。
V01_EXAMPLE_MCP_TOOL_NAMES: frozenset[str] = frozenset({"echo_write_draft"})


class GuardedToolRegistry(ToolRegistry):
    """在注册与执行阶段强制执行工具白名单；并对工具输出做 S&G 输出治理（超长截断）。

    ``max_observation_chars``：工具结果返回后、写入消息（``append_observation``）前的
    最大字符数；``None``/``0`` 表示不截断（默认跟随 ``agent.react.max_tool_observation_chars``）。
    """

    __slots__ = ("_allowed", "_max_observation_chars")

    def __init__(
        self,
        *,
        allowed_names: frozenset[str] | None = None,
        max_observation_chars: int | None = None,
    ) -> None:
        super().__init__()
        self._allowed: frozenset[str] = (
            allowed_names if allowed_names is not None else V01_SG_TOOL_WHITELIST
        )
        self._max_observation_chars = max_observation_chars

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
        result = super().execute(name, arguments)
        cap = self._max_observation_chars
        if cap and cap > 0:
            return filter_tool_output(result, int(cap))
        return result
