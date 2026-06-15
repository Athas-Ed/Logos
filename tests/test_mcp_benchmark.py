"""MCP 工具调用延迟基准测试（长连接 vs 短连接）。

在运行前请确认已安装 ``pytest-benchmark``（或直接作为普通测试执行，仅记录耗时）。
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("mcp")

from logos.platform.mcp_stdio import (
    McpStdioSession,
    call_mcp_tool_sync,
    mcp_server_argv,
    resolve_repo_root,
)


def _stdio_cmd() -> list[str]:
    repo = resolve_repo_root()
    return mcp_server_argv(repo, "skills/example-stdio-mcp/server.py")


# ---------------------------------------------------------------------------
# 长连接：McpStdioSession（背景线程 + 事件循环）
# ---------------------------------------------------------------------------


class TestLongLivedSessionLatency:
    """单次建立会话，连续多次调用，测量平均延迟。"""

    @pytest.fixture(autouse=True)
    def _session(self) -> None:
        cmd = _stdio_cmd()
        self._session = McpStdioSession(cmd)
        yield
        self._session.close()

    def test_long_lived_call_once(self) -> None:
        """长连接：1 次调用基线。"""
        t0 = time.perf_counter()
        out = self._session.call_tool("echo", {"text": "基准测试"})
        elapsed = time.perf_counter() - t0
        assert out == "基准测试"
        self._last_elapsed = elapsed  # 用于后续比较

    def test_long_lived_call_10_times(self) -> None:
        """长连接：10 次连续调用的平均 & 总耗时。"""
        n = 10
        t0 = time.perf_counter()
        for i in range(n):
            out = self._session.call_tool("echo", {"text": f"第{i}次"})
            assert out == f"第{i}次"
        total = time.perf_counter() - t0
        avg = total / n
        # 不硬编码阈值，仅在测试报告中输出
        print(f"\n[benchmark] 长连接 {n} 次调用：总计 {total:.3f}s，平均 {avg*1000:.1f}ms")
        self._avg = avg


# ---------------------------------------------------------------------------
# 短连接：call_mcp_tool_sync（每次启停子进程）
# ---------------------------------------------------------------------------


class TestShortLivedLatency:
    """每次调用起停子进程，测量单次与多次开销。"""

    def test_short_lived_call_once(self) -> None:
        """短连接：1 次调用（含子进程起停 + initialize）。"""
        cmd = _stdio_cmd()
        t0 = time.perf_counter()
        out = call_mcp_tool_sync(cmd, None, "echo", {"text": "基准测试"})
        elapsed = time.perf_counter() - t0
        assert out == "基准测试"
        print(f"\n[benchmark] 短连接 1 次调用：{elapsed*1000:.1f}ms")
        self._last_elapsed = elapsed

    def test_short_lived_call_10_times(self) -> None:
        """短连接：10 次连续调用（每次起停）。"""
        cmd = _stdio_cmd()
        n = 10
        t0 = time.perf_counter()
        for i in range(n):
            out = call_mcp_tool_sync(cmd, None, "echo", {"text": f"第{i}次"})
            assert out == f"第{i}次"
        total = time.perf_counter() - t0
        avg = total / n
        print(f"\n[benchmark] 短连接 {n} 次调用：总计 {total:.3f}s，平均 {avg*1000:.1f}ms")
        self._avg = avg


# ---------------------------------------------------------------------------
# 进程泄漏回归（与 test_mcp_stdio_process_leak.py 互补）
# ---------------------------------------------------------------------------


def test_long_lived_no_process_leak() -> None:
    """长连接：只应有一个子进程（不随工具调用增长）。"""
    psutil = pytest.importorskip("psutil")
    me = psutil.Process()
    before = len(me.children(recursive=True))
    cmd = _stdio_cmd()
    session = McpStdioSession(cmd)
    try:
        for i in range(20):
            out = session.call_tool("echo", {"text": f"第{i}次"})
            assert out == f"第{i}次"
        children = me.children(recursive=True)
        # 子进程数应等于 1（MCP server 进程）+ 测试框架自身的进程
        assert len(children) <= before + 2, (
            f"子进程数异常增长 before={before} after={len(children)}"
        )
    finally:
        session.close()
