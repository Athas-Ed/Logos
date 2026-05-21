"""MCP stdio 示例 Skill 与 GuardedToolRegistry / 沙箱策略的集成测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from logos.agent.react import ReActStreamDone, iter_react_loop
from logos.harness.sg_layer import (
    GuardedToolRegistry,
    V01_EXAMPLE_MCP_TOOL_NAMES,
    build_v01_guarded_tool_registry,
)
from logos.harness.sg_layer.builtin_tool_schemas import WRITE_DRAFT_PARAMETERS
from logos.harness.sg_layer.guarded_registry import V01_SG_TOOL_WHITELIST as _V01_CORE
from logos.harness.sg_layer.mcp_bridge import mcp_tool_summaries, register_mcp_tool_proxies
from logos.harness.sg_layer.mcp_stdio_sync import McpStdioJsonRpcSession, stdio_params_for_example_skill
from logos.ports import AppSettings
from logos.ports.llm import ChatMessage, LLMClient


class _ToolThenAnswerLLM(LLMClient):
    """首轮输出 MCP 工具调用 JSON，次轮输出 final_answer。"""

    def __init__(self) -> None:
        self._turn = 0

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        return "".join(self.stream_completion(messages, json_mode=json_mode))

    def stream_completion(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
    ):
        self._turn += 1
        if self._turn == 1:
            payload = {
                "thought": "调用示例 MCP 工具",
                "action": {
                    "name": "echo_write_draft",
                    "arguments": {"path": "notes/x.md", "content": "hello"},
                },
            }
            yield json.dumps(payload, ensure_ascii=False)
        else:
            yield json.dumps(
                {"thought": "收尾", "final_answer": "mcp-ok"},
                ensure_ascii=False,
            )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        workspace_root=str(tmp_path / "workspace"),
        example_ksfs_root=str(tmp_path / "example_ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / "idx"),
        logs_root=str(tmp_path / "logs"),
        conversations_cache="./workspace/conversations",
        hsi_sqlite_path=str(tmp_path / "idx" / "hsi"),
        chroma_persist_directory=str(tmp_path / "idx" / "chroma"),
        chroma_collection="c",
        embedding_provider="bge_small_zh",
        embedding_model_path="models/x",
    )


def test_mcp_stdio_session_list_and_call_tool() -> None:
    params = stdio_params_for_example_skill(repo_root=_repo_root(), python_exe=sys.executable)
    with McpStdioJsonRpcSession(params) as client:
        lr = client.list_tools()
        names = {t["name"] for t in lr.get("tools", []) if isinstance(t, dict)}
        assert "echo_write_draft" in names
        text = client.call_tool_text("echo_write_draft", {"path": "a.md", "content": "xy"})
        data = json.loads(text)
        assert data.get("ok") is True
        assert data.get("content_bytes") == 2


def test_mcp_tool_schema_aligns_with_builtin_write_draft() -> None:
    params = stdio_params_for_example_skill(repo_root=_repo_root(), python_exe=sys.executable)
    with McpStdioJsonRpcSession(params) as client:
        lr = client.list_tools()
        echo = next(
            t
            for t in lr.get("tools", [])
            if isinstance(t, dict) and t.get("name") == "echo_write_draft"
        )
        schema = echo.get("inputSchema")
        assert isinstance(schema, dict)
        assert set(schema.get("required", [])) == set(WRITE_DRAFT_PARAMETERS["required"])
        mcp_props = set((schema.get("properties") or {}).keys())
        assert {"path", "content"}.issubset(mcp_props)


def test_mcp_progressive_summaries_strip_schema() -> None:
    params = stdio_params_for_example_skill(repo_root=_repo_root(), python_exe=sys.executable)
    with McpStdioJsonRpcSession(params) as client:
        sums = mcp_tool_summaries(client.list_tools())
        assert sums and all("inputSchema" not in s for s in sums)
        assert any(s["name"] == "echo_write_draft" for s in sums)


def test_guarded_registry_blocks_echo_without_whitelist_extension() -> None:
    reg = GuardedToolRegistry()
    with pytest.raises(ValueError, match="白名单"):
        reg.register(
            "echo_write_draft",
            description="x",
            parameters=WRITE_DRAFT_PARAMETERS,
            handler=lambda **_: "n",
        )


def test_registry_proxies_mcp_tool_and_process_exits(tmp_path: Path) -> None:
    params = stdio_params_for_example_skill(repo_root=_repo_root(), python_exe=sys.executable)
    proc_holder: dict[str, int | None] = {"pid": None}
    with McpStdioJsonRpcSession(params) as client:
        assert client._proc is not None
        proc_holder["pid"] = client._proc.pid
        reg = build_v01_guarded_tool_registry(
            _settings(tmp_path),
            extra_allowed_tools=V01_EXAMPLE_MCP_TOOL_NAMES,
        )
        register_mcp_tool_proxies(
            reg,
            client,
            mcp_tool_names=V01_EXAMPLE_MCP_TOOL_NAMES,
        )
        out = reg.execute(
            "echo_write_draft",
            {"path": "rel.md", "content": "body"},
        )
        parsed = json.loads(out)
        assert parsed.get("ok") is True
    assert proc_holder["pid"] is not None


def test_react_uses_mcp_proxied_tool(tmp_path: Path) -> None:
    params = stdio_params_for_example_skill(repo_root=_repo_root(), python_exe=sys.executable)
    with McpStdioJsonRpcSession(params) as client:
        reg = build_v01_guarded_tool_registry(
            _settings(tmp_path),
            extra_allowed_tools=V01_EXAMPLE_MCP_TOOL_NAMES,
        )
        register_mcp_tool_proxies(
            reg,
            client,
            mcp_tool_names=V01_EXAMPLE_MCP_TOOL_NAMES,
        )
        llm = _ToolThenAnswerLLM()
        done = None
        for item in iter_react_loop(
            llm,
            reg,
            "ping",
            max_steps=6,
            stream_assistant=False,
        ):
            if isinstance(item, ReActStreamDone):
                done = item.result
        assert done is not None
        assert done.answer == "mcp-ok"
        assert any(
            m.role == "user" and "content_bytes" in (m.content or "")
            for m in done.messages
        )


def test_v01_whitelist_constant_unchanged_for_builtin_only() -> None:
    assert _V01_CORE == frozenset(
        {"retrieve", "read_ksfs", "list_ksfs", "write_draft"},
    )
    assert V01_EXAMPLE_MCP_TOOL_NAMES == frozenset({"echo_write_draft"})
