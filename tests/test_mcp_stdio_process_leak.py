"""MCP stdio：重复起停子进程后子进程数量应回落（需 psutil，已列入 dev 依赖）。"""

from __future__ import annotations

import os
import time

import pytest

psutil = pytest.importorskip("psutil")

from logos.platform.mcp_stdio import call_mcp_tool_sync, mcp_server_argv, resolve_repo_root


def test_repeated_mcp_calls_do_not_accumulate_children() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/example-stdio-mcp/server.py")
    me = psutil.Process()

    def _child_count() -> int:
        me.children(recursive=True)  # refresh internal cache
        return len(me.children(recursive=True))

    before = _child_count()
    for _ in range(20):
        out = call_mcp_tool_sync(cmd, os.environ, "echo", {"text": "p"})
        assert out == "p"
    # 给操作系统一点时间回收短生命周期子进程
    time.sleep(0.4)
    after = _child_count()
    assert after <= before + 2, f"子进程数异常增长 before={before} after={after}"
