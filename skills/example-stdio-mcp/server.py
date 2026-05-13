"""示例 MCP（stdio）：``echo`` 与 ``echo_write_draft``。

``echo`` 用于进程泄漏与 discover 管线联调；``echo_write_draft`` 的入参 JSON Schema
与内置 ``write_draft`` 一致（见 ``logos.harness.sg_layer.builtin_tool_schemas``），
实现为只读回显，便于集成测试与 Agent 代理接线。
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logos-example-stdio-mcp")


@mcp.tool()
async def echo(text: str) -> str:
    """原样返回传入文本（仅用于联调与自动化测试）。"""
    return text if text is not None else ""


@mcp.tool(
    name="echo_write_draft",
    description=(
        "示例 Skill：不写入磁盘；回显 path 与 content 字节长度。"
        "参数 JSON Schema 与进程内 ``write_draft`` 工具同源。"
    ),
)
def echo_write_draft(path: str, content: str) -> str:
    return json.dumps(
        {"ok": True, "path": path, "content_bytes": len(content.encode("utf-8"))},
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
