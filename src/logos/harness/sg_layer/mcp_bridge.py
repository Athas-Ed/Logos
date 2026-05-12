"""将 MCP ``tools/list`` 中的工具以受控名称注册到 :class:`~logos.harness.sg_layer.guarded_registry.GuardedToolRegistry`。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from logos.harness.sg_layer.guarded_registry import GuardedToolRegistry

from .mcp_stdio_sync import McpStdioJsonRpcSession


def register_mcp_tool_proxies(
    registry: GuardedToolRegistry,
    client: McpStdioJsonRpcSession,
    *,
    mcp_tool_names: frozenset[str],
) -> None:
    """按 MCP 返回的 *inputSchema* 注册代理工具；仅处理 *mcp_tool_names* 子集（与 S&G 白名单对齐）。"""
    raw = client.list_tools()
    tools = raw.get("tools")
    if not isinstance(tools, list):
        msg = "tools/list 响应缺少 tools 列表"
        raise ValueError(msg)
    registered: set[str] = set()
    for spec in tools:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name")
        if not isinstance(name, str) or name not in mcp_tool_names:
            continue
        desc = spec.get("description") if isinstance(spec.get("description"), str) else ""
        params = spec.get("inputSchema")
        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}

        def _make(nm: str) -> Callable[..., str]:
            def handler(**kwargs: Any) -> str:
                return client.call_tool_text(nm, kwargs)

            return handler

        registry.register(
            name,
            description=desc,
            parameters=params,
            handler=_make(name),
        )
        registered.add(name)
    missing = mcp_tool_names - registered
    if missing:
        msg = f"MCP 未返回以下工具，无法注册代理: {sorted(missing)!r}"
        raise ValueError(msg)


def mcp_tool_summaries(tools_payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """渐进式披露：仅名称与说明（不含 inputSchema），便于拼装提示词或 UI。"""
    tools = tools_payload.get("tools")
    if not isinstance(tools, list):
        return []
    out: list[dict[str, str]] = []
    for spec in tools:
        if not isinstance(spec, dict):
            continue
        n = spec.get("name")
        if not isinstance(n, str):
            continue
        d = spec.get("description")
        out.append(
            {
                "name": n,
                "description": d if isinstance(d, str) else "",
            }
        )
    return out
