"""MCP：高德天气 skill 发现与经 GuardedToolRegistry 调用（无真实 Key 时不打外网）。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from logos.harness.mcp_stdio import (
    call_mcp_tool_sync,
    discover_mcp_tools_sync,
    mcp_server_argv,
    resolve_repo_root,
)
from logos.harness.sg_layer import build_v01_guarded_tool_registry
from logos.ports import AppSettings, McpServerEntry


def _amap_entry(*, enabled: bool, key: str) -> McpServerEntry:
    env: frozenset[tuple[str, str]] = frozenset()
    if key.strip():
        env = frozenset({("AMAP_WEB_KEY", key.strip())})
    return McpServerEntry(
        id="amap_weather",
        enabled=enabled,
        entrypoint="skills/amap-weather-mcp/server.py",
        strip_http_proxy=True,
        env=env,
    )


def test_resolve_repo_root_finds_marker_server() -> None:
    from logos.harness.mcp_stdio import _marker_skill_server, resolve_repo_root

    assert _marker_skill_server(resolve_repo_root()).is_file()


def test_amap_server_script_exists() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/amap-weather-mcp/server.py")
    assert Path(cmd[1]).is_file()


def test_mcp_discover_lists_query_weather() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/amap-weather-mcp/server.py")
    tools = discover_mcp_tools_sync(cmd, os.environ)
    names = {t.name for t in tools}
    assert "query_weather" in names


def test_mcp_call_without_key_returns_hint() -> None:
    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/amap-weather-mcp/server.py")
    out = call_mcp_tool_sync(cmd, os.environ, "query_weather", {"city": "北京"})
    assert "error:" in out
    assert "AMAP_WEB_KEY" in out or "mcp_servers" in out


def test_mcp_call_works_when_parent_has_running_event_loop() -> None:
    """regression：在已有 asyncio loop 的协程里调用 tools/call，不得再嵌套 asyncio.run 抛错。"""

    import asyncio

    repo = resolve_repo_root()
    cmd = mcp_server_argv(repo, "skills/amap-weather-mcp/server.py")

    async def _in_loop() -> str:
        return call_mcp_tool_sync(cmd, os.environ, "query_weather", {"city": "北京"})

    out = asyncio.run(_in_loop())
    assert "error:" in out


def _minimal_settings(
    tmp_path: Path, *, mcp: tuple[McpServerEntry, ...]
) -> AppSettings:
    return AppSettings(
        workspace_root=str(tmp_path / "ws"),
        example_ksfs_root=str(tmp_path / "ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / "idx"),
        logs_root=str(tmp_path / "logs"),
        conversations_cache="./workspace/conversations",
        hsi_sqlite_path=str(tmp_path / "idx" / "hsi"),
        chroma_persist_directory=str(tmp_path / "idx" / "chroma"),
        chroma_collection="c",
        embedding_provider="bge_small_zh",
        embedding_model_path="models/x",
        mcp_servers=mcp,
    )


def test_registry_without_amap_has_no_query_weather(tmp_path: Path) -> None:
    s = _minimal_settings(tmp_path, mcp=())
    reg = build_v01_guarded_tool_registry(s)
    assert "query_weather" not in reg.names()


def test_registry_with_amap_registers_query_weather(tmp_path: Path) -> None:
    s = _minimal_settings(tmp_path, mcp=(_amap_entry(enabled=True, key=""),))
    reg = build_v01_guarded_tool_registry(s)
    assert "query_weather" in reg.names()
    obs = reg.execute("query_weather", {"city": "上海"})
    assert "error:" in obs


@pytest.mark.skipif(
    not (os.environ.get("LOGOS_AMAP_E2E_KEY") or "").strip(),
    reason="需要环境变量 LOGOS_AMAP_E2E_KEY 才跑真实高德请求",
)
def test_registry_query_weather_live(tmp_path: Path) -> None:
    key = os.environ["LOGOS_AMAP_E2E_KEY"].strip()
    s = _minimal_settings(tmp_path, mcp=(_amap_entry(enabled=True, key=key),))
    reg = build_v01_guarded_tool_registry(s)
    obs = reg.execute("query_weather", {"city": "110101"})
    assert "error:" not in obs
    assert "气温" in obs or "天气" in obs
