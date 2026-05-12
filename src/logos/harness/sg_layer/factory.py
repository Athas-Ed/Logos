"""基于 :class:`~logos.ports.settings.AppSettings` 组装带沙箱的 V0.1 工具注册表。"""

from __future__ import annotations

import json
from pathlib import Path

from logos.ports import AppSettings
from logos.ports.retrieval import Citation, RetrievalService

from logos.tools.workspace_paths import read_text_under_root, write_draft_under_workspace

from .builtin_tool_schemas import (
    READ_KSFS_PARAMETERS,
    RETRIEVE_PARAMETERS,
    WRITE_DRAFT_PARAMETERS,
)
from .guarded_registry import GuardedToolRegistry, V01_SG_TOOL_WHITELIST


class _EmptyRetrieval:
    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        return []


def build_v01_guarded_tool_registry(
    settings: AppSettings,
    *,
    retrieval: RetrievalService | None = None,
    citation_sink: list[Citation] | None = None,
    extra_allowed_tools: frozenset[str] | None = None,
) -> GuardedToolRegistry:
    """注册 ``retrieve`` / ``read_ksfs`` / ``write_draft``（白名单子集）。

    *extra_allowed_tools* 用于接入经 MCP 代理的示例工具名等；须与后续 :func:`~logos.harness.sg_layer.mcp_bridge.register_mcp_tool_proxies` 注册名一致。
    """
    allowed = V01_SG_TOOL_WHITELIST | (extra_allowed_tools or frozenset())
    reg = GuardedToolRegistry(allowed_names=allowed)
    workspace = Path(settings.workspace_root).resolve()
    ksfs_root = Path(settings.ksfs_root).resolve()
    rsvc: RetrievalService = retrieval if retrieval is not None else _EmptyRetrieval()

    def _retrieve(text: str, top_k: int = 8) -> str:
        q = (text or "").strip()
        if not q:
            return "error: retrieve 需要非空查询文本"
        cites = rsvc.query(text=q, top_k=int(top_k))
        if citation_sink is not None:
            citation_sink.extend(cites)
        payload = [
            {"path": c.path, "snippet": c.snippet, "score": c.score} for c in cites
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _read_ksfs(path: str) -> str:
        return read_text_under_root(
            ksfs_root,
            path,
            context_label="KSFS 根",
            denied_operation="read_ksfs",
        )

    def _write_draft(path: str, content: str) -> str:
        return write_draft_under_workspace(workspace, path, content)

    reg.register(
        "retrieve",
        description="按查询文本检索知识库，返回 path/snippet/score 列表（JSON 数组字符串）。",
        parameters=RETRIEVE_PARAMETERS,
        handler=_retrieve,
    )
    reg.register(
        "read_ksfs",
        description="只读打开 KSFS 根（paths.ksfs_root）下的相对路径 Markdown/文本（禁止绝对路径与 ..）。",
        parameters=READ_KSFS_PARAMETERS,
        handler=_read_ksfs,
    )
    reg.register(
        "write_draft",
        description="将完整草稿内容写入 workspace 下的相对路径（禁止写出 workspace 外）。",
        parameters=WRITE_DRAFT_PARAMETERS,
        handler=_write_draft,
    )
    return reg
