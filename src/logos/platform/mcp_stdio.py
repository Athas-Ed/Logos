"""MCP stdio 客户端桥接：短连接 discover / call_tool（与同步 ReAct 兼容）。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

_log = logging.getLogger("logos.platform.mcp_stdio")

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.types import CallToolResult
except ImportError as exc:  # pragma: no cover — 仅在未安装 mcp 的环境触发
    ClientSession = None  # type: ignore[misc, assignment]
    StdioServerParameters = None  # type: ignore[misc, assignment]
    stdio_client = None  # type: ignore[misc, assignment]
    CallToolResult = None  # type: ignore[misc, assignment]
    _MCP_IMPORT_ERROR: ImportError | None = exc
else:
    _MCP_IMPORT_ERROR = None


def _run_coroutine_in_worker_thread(factory: Callable[[], Any], *, timeout_s: float = 120.0) -> Any:
    """在独立线程中 ``asyncio.run(factory())``，避免 uvicorn/FastAPI 流式响应已在事件循环内时嵌套 ``asyncio.run`` 失败。"""

    def _worker() -> Any:
        return asyncio.run(factory())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result(timeout=timeout_s)


def require_mcp_sdk_installed() -> None:
    """若未安装 ``mcp`` 包则抛出带安装指引的 :exc:`ImportError`（与后端所用解释器一致）。"""
    if _MCP_IMPORT_ERROR is not None or ClientSession is None:
        exe = sys.executable
        msg = (
            f"当前 Python 未安装 MCP SDK（import mcp 失败）。请在与启动后端相同的解释器中执行：\n"
            f'  "{exe}" -m pip install "mcp>=1.2.0"\n'
            "或在仓库根执行：pip install -e .\n"
            "安装后请重启后端进程。"
        )
        raise ImportError(msg) from _MCP_IMPORT_ERROR


def _marker_skill_server(repo: Path) -> Path:
    """用于定位仓库根：优先示例 MCP，其次高德（便于仅检出部分目录时的回退）。"""
    for rel in (
        Path("skills") / "example-stdio-mcp" / "server.py",
        Path("skills") / "amap-weather-mcp" / "server.py",
    ):
        p = repo / rel
        if p.is_file():
            return p
    return repo / "skills" / "example-stdio-mcp" / "server.py"


def resolve_repo_root() -> Path:
    """定位含 ``skills/`` 的仓库根。

    1. 环境变量 ``LOGOS_REPO_ROOT``（若指向的目录下存在标记用 ``server.py``）。
    2. 自 ``logos`` 包路径向上查找含 ``skills/example-stdio-mcp/server.py`` 或 ``skills/amap-weather-mcp/server.py`` 的目录。
    3. 回退：``<repo>/src/logos`` 的上两级（兼容可编辑安装时的旧约定）。

    非 ``pip install -e .`` 时 ``logos`` 可能在 site-packages，必须用 1 或 2 才能找到 ``skills/``。
    """
    import logos

    env_root = (os.environ.get("LOGOS_REPO_ROOT") or "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if _marker_skill_server(p).is_file():
            return p
        _log.warning(
            "LOGOS_REPO_ROOT=%s 下未找到 skills/*/server.py（MCP 标记），将忽略该环境变量",
            env_root,
        )

    start = Path(logos.__file__).resolve().parent
    for base in [start, *start.parents]:
        if _marker_skill_server(base).is_file():
            return base

    fallback = start.parent.parent
    _log.debug(
        "未在目录链上发现 MCP 标记脚本，回退为 %s（MCP 可能无法挂载）",
        fallback,
    )
    return fallback


def mcp_server_argv(repo: Path, entrypoint: str) -> list[str]:
    """``[sys.executable, <resolved server.py>]``；*entrypoint* 为相对 *repo* 的正斜杠或系统路径均可。"""
    script = (repo / Path(entrypoint)).resolve()
    return [sys.executable, str(script)]


def _call_tool_result_to_text(result: Any) -> str:
    require_mcp_sdk_installed()
    assert CallToolResult is not None

    if not isinstance(result, CallToolResult):
        return json.dumps(result, ensure_ascii=False, default=str)
    if getattr(result, "isError", False):
        parts_err: list[str] = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                parts_err.append(getattr(block, "text", "") or "")
            elif hasattr(block, "text"):
                parts_err.append(str(getattr(block, "text", "")))
        err_body = "\n".join(p for p in parts_err if p).strip()
        if err_body and not err_body.lower().startswith("error"):
            return f"error: {err_body}"
        return err_body or "error: MCP 工具返回 isError 且无文本内容"
    parts: list[str] = []
    for block in result.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(getattr(block, "text", "") or "")
        elif hasattr(block, "text"):
            parts.append(str(getattr(block, "text", "")))
    body = "\n".join(p for p in parts if p).strip()
    if body:
        return body
    return json.dumps(
        [c.model_dump() for c in result.content],
        ensure_ascii=False,
    )


async def _with_stdio_session(
    command: list[str],
    env: Mapping[str, str] | None,
    work: Callable[..., Any],
    *,
    cwd: str | Path | None = None,
) -> Any:
    require_mcp_sdk_installed()
    assert ClientSession is not None
    assert StdioServerParameters is not None
    assert stdio_client is not None

    if not command:
        msg = "MCP stdio command 为空"
        raise ValueError(msg)
    params = StdioServerParameters(
        command=command[0],
        args=command[1:],
        env=dict(env) if env is not None else None,
        cwd=cwd,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await work(session)


async def _discover(session: Any) -> list[Any]:
    listed = await session.list_tools()
    return list(listed.tools)


def discover_mcp_tools_sync(
    command: list[str],
    env: Mapping[str, str] | None = None,
    *,
    cwd: str | Path | None = None,
) -> list[Any]:
    """连接 MCP Server，执行 ``tools/list`` 后断开。"""

    async def _run() -> list[Any]:
        return await _with_stdio_session(command, env, _discover, cwd=cwd)

    return _run_coroutine_in_worker_thread(lambda: _run())


async def _call_named_tool(
    session: Any, tool_name: str, arguments: Mapping[str, Any]
) -> str:
    result = await session.call_tool(
        tool_name,
        arguments=dict(arguments or {}),
    )
    return _call_tool_result_to_text(result)


def call_mcp_tool_sync(
    command: list[str],
    env: Mapping[str, str] | None,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
    *,
    cwd: str | Path | None = None,
) -> str:
    """单次 ``tools/call``（每次调用启停子进程）。"""

    async def _work(session: Any) -> str:
        return await _call_named_tool(session, tool_name, arguments or {})

    return _run_coroutine_in_worker_thread(
        lambda: _with_stdio_session(command, env, _work, cwd=cwd)
    )


def make_stdio_mcp_tool_handler(
    command: list[str],
    env: Mapping[str, str] | None,
    tool_name: str,
    *,
    cwd: str | Path | None = None,
) -> Callable[..., str]:
    """返回可注册到 :class:`~logos.agent.tool_registry.ToolRegistry` 的同步 handler。"""

    def _handler(**kwargs: Any) -> str:
        try:
            return call_mcp_tool_sync(command, env, tool_name, kwargs, cwd=cwd)
        except Exception as exc:  # noqa: BLE001 — 工具观测需可读
            _log.exception("MCP tools/call 失败 tool=%s", tool_name)
            return f"error: MCP 调用失败 — {type(exc).__name__}: {exc}"

    return _handler
