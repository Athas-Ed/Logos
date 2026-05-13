"""MCP：示例 echo skill 经通用管线 discover / registry。"""

from __future__ import annotations

import os
from pathlib import Path

from logos.harness.mcp_stdio import (
    call_mcp_tool_sync,
    discover_mcp_tools_sync,
    mcp_server_argv,
    resolve_repo_root,
)
from logos.harness.sg_layer import build_v01_guarded_tool_registry
from logos.ports import AppSettings, McpServerEntry


def test_discover_echo_tool() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/example-stdio-mcp/server.py")
    tools = discover_mcp_tools_sync(cmd, os.environ)
    assert {t.name for t in tools} >= {"echo"}


def test_call_echo_roundtrip() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/example-stdio-mcp/server.py")
    out = call_mcp_tool_sync(cmd, os.environ, "echo", {"text": "你好"})
    assert out == "你好"


def test_registry_mounts_echo(tmp_path: Path) -> None:
    entry = McpServerEntry(
        id="example_echo",
        enabled=True,
        entrypoint="skills/example-stdio-mcp/server.py",
        strip_http_proxy=False,
        env=frozenset(),
    )
    s = AppSettings(
        workspace_root=str(tmp_path / "ws"),
        example_ksfs_root=str(tmp_path / "ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / "idx"),
        logs_root=str(tmp_path / "logs"),
        hsi_sqlite_path=str(tmp_path / "idx" / "hsi"),
        chroma_persist_directory=str(tmp_path / "idx" / "chroma"),
        chroma_collection="c",
        embedding_provider="bge_small_zh",
        embedding_model_path="models/x",
        mcp_servers=(entry,),
    )
    reg = build_v01_guarded_tool_registry(s)
    assert "echo" in reg.names()
    assert reg.execute("echo", {"text": "x"}) == "x"
