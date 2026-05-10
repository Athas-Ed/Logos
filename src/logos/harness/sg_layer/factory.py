"""基于 :class:`~logos.ports.settings.AppSettings` 组装带沙箱的 V0.1 工具注册表。"""

from __future__ import annotations

import json
from pathlib import Path

from logos.ports import AppSettings
from logos.ports.retrieval import Citation, RetrievalService

from .guarded_registry import GuardedToolRegistry, V01_SG_TOOL_WHITELIST
from .path_sandbox import (
    PathSandboxViolationError,
    resolve_path_under_root,
    write_draft_under_workspace,
)


class _EmptyRetrieval:
    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        return []


def build_v01_guarded_tool_registry(
    settings: AppSettings,
    *,
    retrieval: RetrievalService | None = None,
    citation_sink: list[Citation] | None = None,
    max_output_chars: int = 100_000,
) -> GuardedToolRegistry:
    """注册 ``retrieve`` / ``read_lkc`` / ``write_draft``（V0.1 白名单子集）。"""
    reg = GuardedToolRegistry(
        allowed_names=V01_SG_TOOL_WHITELIST,
        max_output_chars=max_output_chars,
    )
    workspace = Path(settings.workspace_root).resolve()
    lkc_root = Path(settings.lkc_root).resolve()
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

    def _read_lkc(path: str) -> str:
        try:
            target = resolve_path_under_root(lkc_root, path)
        except PathSandboxViolationError as exc:
            return f"error: read_lkc 被拒绝 — {exc}"
        if not target.is_file():
            return f"error: 未找到文件（相对 LKC 根）{path!r}"
        try:
            return target.read_text(encoding="utf-8")
        except OSError as exc:
            return f"error: 读取失败 — {exc}"

    def _write_draft(path: str, content: str) -> str:
        return write_draft_under_workspace(workspace, path, content)

    reg.register(
        "retrieve",
        description="按查询文本检索知识库，返回 path/snippet/score 列表（JSON 数组字符串）。",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "检索查询"},
                "top_k": {
                    "type": "integer",
                    "description": "返回条数上限，默认 8",
                    "default": 8,
                },
            },
            "required": ["text"],
        },
        handler=_retrieve,
    )
    reg.register(
        "read_lkc",
        description="只读打开 LKC 根下的相对路径 Markdown/文本（禁止绝对路径与 ..）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于 LKC 根的路径，如 entities/10001/profile.md",
                },
            },
            "required": ["path"],
        },
        handler=_read_lkc,
    )
    reg.register(
        "write_draft",
        description="将完整草稿内容写入 workspace 下的相对路径（禁止写出 workspace 外）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于 workspace 根的路径，例如 notes/ch1.md",
                },
                "content": {"type": "string", "description": "文件完整文本"},
            },
            "required": ["path", "content"],
        },
        handler=_write_draft,
    )
    return reg
