"""基于 :class:`~logos.ports.settings.AppSettings` 组装带沙箱的 V0.1 工具注册表。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from logos.harness.mcp_stdio import (
    amap_weather_mcp_command,
    discover_mcp_tools_sync,
    make_stdio_mcp_tool_handler,
)
from logos.ports import AppSettings
from logos.ports.retrieval import Citation, RetrievalService
from logos.tools.ksfs_list import list_ksfs_entries

from .guarded_registry import GuardedToolRegistry, V01_SG_TOOL_WHITELIST
from .path_sandbox import (
    PathSandboxViolationError,
    resolve_path_under_root,
    write_draft_under_workspace,
)

_log = logging.getLogger(__name__)

# MCP 子进程不应继承宿主为 LLM 配的 HTTP 代理去访问高德（易被 CONNECT/证书 干扰）
_AMAP_MCP_STRIP_PROXY_KEYS: frozenset[str] = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    }
)


def _amap_mcp_child_env(settings: AppSettings) -> dict[str, str]:
    env = {k: str(v) for k, v in os.environ.items() if isinstance(v, str)}
    for k in _AMAP_MCP_STRIP_PROXY_KEYS:
        env.pop(k, None)
    key = (settings.skills_amap_weather_web_api_key or "").strip()
    if key:
        env["AMAP_WEB_KEY"] = key
    return env


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
    """注册 ``retrieve`` / ``read_ksfs`` / ``list_ksfs`` / ``write_draft``；可选挂载高德天气 MCP 工具。"""
    mcp_tool_specs: list[Any] = []
    amap_cmd: list[str] | None = None
    amap_env: dict[str, str] | None = None
    if settings.skills_amap_weather_enabled:
        cmd = amap_weather_mcp_command()
        script = Path(cmd[1])
        if not script.is_file():
            _log.warning(
                "高德天气 MCP 脚本不存在，已跳过：%s。"
                "若 logos 安装在 site-packages，请设置环境变量 LOGOS_REPO_ROOT 指向本仓库根，"
                "或使用 pip install -e .",
                script,
            )
        else:
            amap_cmd, amap_env = cmd, _amap_mcp_child_env(settings)
            try:
                discovered = discover_mcp_tools_sync(amap_cmd, amap_env)
            except ImportError as exc:
                _log.error(
                    "高德天气 MCP 未挂载（缺少 Python 包 mcp 或依赖不完整）：%s",
                    exc,
                )
            except Exception:  # noqa: BLE001
                _log.exception("MCP tools/list 失败（高德天气）")
            else:
                for t in discovered:
                    if t.name in V01_SG_TOOL_WHITELIST:
                        _log.warning("忽略与内置工具同名的 MCP 工具：%s", t.name)
                        continue
                    mcp_tool_specs.append(t)
                if mcp_tool_specs:
                    _log.info(
                        "已挂载高德天气 MCP 工具：%s",
                        ", ".join(t.name for t in mcp_tool_specs),
                    )
                elif not mcp_tool_specs:
                    _log.warning(
                        "skills.amap_weather.enabled 为 true 但 MCP 未注册任何工具（tools/list 为空或均被过滤）"
                    )

    extra_names = frozenset(t.name for t in mcp_tool_specs)
    allowed = V01_SG_TOOL_WHITELIST | extra_names
    reg = GuardedToolRegistry(
        allowed_names=allowed,
        max_output_chars=max_output_chars,
    )
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
        try:
            target = resolve_path_under_root(ksfs_root, path)
        except PathSandboxViolationError as exc:
            return f"error: read_ksfs 被拒绝 — {exc}"
        if not target.is_file():
            return f"error: 未找到文件（相对 KSFS 根）{path!r}"
        try:
            return target.read_text(encoding="utf-8")
        except OSError as exc:
            return f"error: 读取失败 — {exc}"

    def _list_ksfs(
        path: str = "",
        recursive: bool = False,
        max_entries: int = 200,
    ) -> str:
        return list_ksfs_entries(
            ksfs_root,
            path,
            recursive=bool(recursive),
            max_entries=int(max_entries),
        )

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
        "read_ksfs",
        description="只读打开 KSFS 根（paths.ksfs_root）下的相对路径 Markdown/文本（禁止绝对路径与 ..）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于 KSFS 根的路径，如 Test/note.md",
                },
            },
            "required": ["path"],
        },
        handler=_read_ksfs,
    )
    reg.register(
        "list_ksfs",
        description="列出 KSFS 根下某目录中的子项（仅 .md/.txt 与目录名；path 空=根目录；recursive 默认 false）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对 KSFS 根的目录，如 Test；留空表示根",
                    "default": "",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出（仍受 max_entries 限制）",
                    "default": False,
                },
                "max_entries": {
                    "type": "integer",
                    "description": "最多返回条数，默认 200，上限 1000",
                    "default": 200,
                },
            },
            "required": [],
        },
        handler=_list_ksfs,
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
    if mcp_tool_specs and amap_cmd is not None and amap_env is not None:
        for t in mcp_tool_specs:
            params: dict[str, Any]
            if isinstance(t.inputSchema, dict):
                params = t.inputSchema
            else:
                params = {"type": "object", "properties": {}}
            reg.register(
                t.name,
                description=t.description or f"MCP 工具 {t.name}",
                parameters=params,
                handler=make_stdio_mcp_tool_handler(amap_cmd, amap_env, t.name),
            )
    return reg
