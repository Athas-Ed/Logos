"""示例 MCP（stdio）：``echo`` 工具，用于验证通用 ``skills.mcp_servers`` 挂载管线。

与 ``skills/amap-weather-mcp/server.py`` 相同，使用 FastMCP + stdio；无密钥、无外网。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logos-example-echo")


@mcp.tool()
async def echo(text: str) -> str:
    """原样返回传入文本（仅用于联调与自动化测试）。"""
    return text if text is not None else ""


if __name__ == "__main__":
    mcp.run(transport="stdio")
