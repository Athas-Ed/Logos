"""基于 :class:`~logos.ports.settings.AppSettings` 组装带沙箱的 V0.1 工具注册表。"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from logos.platform.mcp_stdio import (
    discover_mcp_tools_sync,
    make_stdio_mcp_tool_handler,
    mcp_server_argv,
    resolve_repo_root,
)
from logos.ports import AppSettings, McpServerEntry
from logos.ports.retrieval import Citation, RetrievalService
from logos.tools.ksfs_list import list_ksfs_entries

from .builtin_tool_schemas import (
    LIST_DRAFTS_PARAMETERS,
    PROMOTE_DRAFT_PARAMETERS,
    READ_DRAFT_PARAMETERS,
    READ_KSFS_PARAMETERS,
    RETRIEVE_PARAMETERS,
    WRITE_DRAFT_PARAMETERS,
)
from .guarded_registry import GuardedToolRegistry, V01_SG_TOOL_WHITELIST
from .path_sandbox import read_text_under_root, write_draft_under_workspace

_log = logging.getLogger(__name__)

_mcp_discovery_cache: dict[
    tuple[Any, ...],
    tuple[tuple[Any, ...], tuple[tuple[Any, list[str], dict[str, str]], ...]],
] = {}
_mcp_discovery_lock = threading.Lock()

_STRIP_HTTP_PROXY_KEYS: frozenset[str] = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    }
)


def _mcp_child_env(entry: McpServerEntry) -> dict[str, str]:
    env = {k: str(v) for k, v in os.environ.items() if isinstance(v, str)}
    if entry.strip_http_proxy:
        for k in _STRIP_HTTP_PROXY_KEYS:
            env.pop(k, None)
    for k, v in entry.env:
        env[k] = v
    return env


def clear_mcp_discovery_cache() -> None:
    """清空 MCP ``tools/list`` 结果缓存（供测试或显式重载配置后调用；生产一般不需要）。"""

    with _mcp_discovery_lock:
        _mcp_discovery_cache.clear()


def _mcp_discovery_cache_key(settings: AppSettings) -> tuple[Any, ...]:
    """缓存键：仓库根、各启用项路径存在性 / mtime，避免 entrypoint 从缺失变为存在仍命中空结果。"""

    repo = resolve_repo_root().resolve()
    parts: list[Any] = [str(repo)]
    for e in settings.mcp_servers:
        if not e.enabled:
            parts.append(("disabled", e.id))
            continue
        script = (repo / Path(e.entrypoint)).resolve()
        if script.is_file():
            parts.append(
                (
                    e.id,
                    e.entrypoint,
                    e.strip_http_proxy,
                    tuple(sorted(e.env)),
                    int(script.stat().st_mtime_ns),
                )
            )
        else:
            parts.append(
                (
                    e.id,
                    e.entrypoint,
                    e.strip_http_proxy,
                    tuple(sorted(e.env)),
                    f"missing:{script}",
                )
            )
    return tuple(parts)


class _EmptyRetrieval:
    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        return []


def _tool_in_skill_scope(name: str, scoped: frozenset[str] | None) -> bool:
    """*scoped* 为 ``None`` 时保留 V0.1 全量内置工具；否则仅 manifest 白名单内的名称可注册。"""
    return scoped is None or name in scoped


def build_v01_guarded_tool_registry(
    settings: AppSettings,
    *,
    retrieval: RetrievalService | None = None,
    citation_sink: list[Citation] | None = None,
    extra_allowed_tools: frozenset[str] | None = None,
    allowed_tools: frozenset[str] | None = None,
) -> GuardedToolRegistry:
    """注册 ``retrieve`` / ``read_ksfs`` / ``list_ksfs`` / ``write_draft``；按配置挂载 MCP 工具。

    *allowed_tools*：产品 Skill manifest 工具白名单；``None`` 表示未按 Skill 裁剪（V0.1 全量内置 + MCP）。
    空集合表示不注册任何工具（如 ``lint_zh``）。
    """
    scoped = allowed_tools
    seen_mcp_tool_names: set[str] = set()
    repo = resolve_repo_root()

    if scoped is not None and len(scoped) == 0:
        mcp_tool_specs = []
        mcp_handlers = []
    else:
        cache_key = _mcp_discovery_cache_key(settings)
        with _mcp_discovery_lock:
            cached = _mcp_discovery_cache.get(cache_key)
        if cached is not None:
            mcp_tool_specs = list(cached[0])
            mcp_handlers = list(cached[1])
        else:
            mcp_tool_specs = []
            mcp_handlers = []
            for entry in settings.mcp_servers:
                if not entry.enabled:
                    continue
                script = (repo / Path(entry.entrypoint)).resolve()
                if not script.is_file():
                    _log.warning(
                        "MCP 技能 %s 的 entrypoint 不存在，已跳过：%s（可设置 LOGOS_REPO_ROOT）",
                        entry.id,
                        script,
                    )
                    continue
                cmd = mcp_server_argv(repo, entry.entrypoint)
                child_env = _mcp_child_env(entry)
                try:
                    discovered = discover_mcp_tools_sync(cmd, child_env, cwd=repo)
                except ImportError as exc:
                    _log.error(
                        "MCP 技能 %s 未挂载（缺少 Python 包 mcp 等）：%s",
                        entry.id,
                        exc,
                    )
                except Exception:  # noqa: BLE001
                    _log.exception("MCP tools/list 失败（技能 id=%s）", entry.id)
                else:
                    for t in discovered:
                        if t.name in V01_SG_TOOL_WHITELIST:
                            _log.warning(
                                "忽略与内置工具同名的 MCP 工具：%s（来自 %s）",
                                t.name,
                                entry.id,
                            )
                            continue
                        if t.name in seen_mcp_tool_names:
                            _log.warning(
                                "忽略重名 MCP 工具：%s（来自 %s，已先由其它技能注册）",
                                t.name,
                                entry.id,
                            )
                            continue
                        seen_mcp_tool_names.add(t.name)
                        mcp_tool_specs.append(t)
                        mcp_handlers.append((t, cmd, child_env))
                    if not discovered:
                        _log.warning(
                            "MCP 技能 %s 已启用但 tools/list 为空",
                            entry.id,
                        )

            with _mcp_discovery_lock:
                _mcp_discovery_cache[cache_key] = (
                    tuple(mcp_tool_specs),
                    tuple(tuple(h) for h in mcp_handlers),
                )

    extra_names = frozenset(t.name for t in mcp_tool_specs)
    extras = extra_allowed_tools or frozenset()
    if scoped is None:
        allowed = V01_SG_TOOL_WHITELIST | extra_names | extras
    else:
        mcp_in_scope = frozenset(n for n in extra_names if n in scoped)
        allowed = (scoped & V01_SG_TOOL_WHITELIST) | mcp_in_scope | (extras & scoped)
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

    def _list_drafts(
        path: str = "",
        recursive: bool = True,
        max_entries: int = 200,
    ) -> str:
        root = workspace
        base = root
        raw = (path or "").strip().replace("\\", "/")
        if raw:
            from logos.platform.sg_layer.path_sandbox import resolve_path_under_root
            try:
                base = resolve_path_under_root(root, raw)
            except ValueError as exc:
                return json.dumps({"error": str(exc)}, ensure_ascii=False)
        if not base.is_dir():
            return json.dumps({"error": f"目录不存在：{raw or '.'!r}"}, ensure_ascii=False)
        cap = max(1, min(int(max_entries), 1000))
        out: list[dict[str, str | int]] = []

        def _rel_of(p: Path) -> str:
            return p.resolve().relative_to(root.resolve()).as_posix()

        def _visit(d: Path) -> None:
            if len(out) >= cap:
                return
            try:
                children = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            except OSError:
                return
            for entry in children:
                if len(out) >= cap:
                    break
                if entry.name.startswith("."):
                    continue
                if entry.name == "README.md":
                    continue
                if entry.is_dir():
                    if _rel_of(entry) == "conversations":
                        continue
                    out.append({"kind": "dir", "name": entry.name, "path": _rel_of(entry)})
                    if recursive:
                        _visit(entry)
                else:
                    if entry.suffix.lower() not in (".md", ".markdown", ".txt"):
                        continue
                    st = entry.stat()
                    out.append({
                        "kind": "file",
                        "name": entry.name,
                        "path": _rel_of(entry),
                        "size_bytes": st.st_size,
                        "last_modified": st.st_mtime_ns,
                    })

        if recursive:
            _visit(base)
        else:
            try:
                for entry in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                    if len(out) >= cap:
                        break
                    if entry.name.startswith("."):
                        continue
                    if entry.name == "README.md":
                        continue
                    if entry.is_dir():
                        if _rel_of(entry) == "conversations":
                            continue
                        out.append({"kind": "dir", "name": entry.name, "path": _rel_of(entry)})
                    else:
                        if entry.suffix.lower() not in (".md", ".markdown", ".txt"):
                            continue
                        st = entry.stat()
                        out.append({
                            "kind": "file",
                            "name": entry.name,
                            "path": _rel_of(entry),
                            "size_bytes": st.st_size,
                            "last_modified": st.st_mtime_ns,
                        })
            except OSError as exc:
                return json.dumps({"error": str(exc)}, ensure_ascii=False)
        return json.dumps({"entries": out, "truncated": len(out) >= cap}, ensure_ascii=False)

    def _read_draft(path: str) -> str:
        return read_text_under_root(
            workspace,
            path,
            context_label="workspace 根",
            denied_operation="read_draft",
        )

    def _promote_draft(items: list[str]) -> str:
        from logos.ports.draft_promotion import PromotionItem
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        if not items:
            return json.dumps({"error": "items 不能为空"}, ensure_ascii=False)
        hsi_db = Path(settings.hsi_sqlite_path).resolve()
        port = FilesystemDraftPromotionPort(hsi_db=hsi_db)
        candidate_items: list[PromotionItem] = []
        for rel in items:
            src = (workspace / rel).resolve()
            try:
                src.relative_to(workspace)
            except ValueError:
                return json.dumps(
                    {"error": f"路径越界：{rel!r}"}, ensure_ascii=False
                )
            if not src.is_file():
                return json.dumps(
                    {"error": f"草稿不存在：{rel!r}"}, ensure_ascii=False
                )
            st = src.stat()
            candidate_items.append(
                PromotionItem(
                    draft_relpath=rel,
                    proposed_ksfs_relpath=rel,
                    draft_mtime_ns=st.st_mtime_ns,
                )
            )
        report = port.apply_promotion(workspace, ksfs_root, candidate_items)
        return json.dumps(
            {
                "ok": report.ok,
                "promoted": list(report.applied),
                "skipped": list(report.skipped),
                "notes": report.notes,
            },
            ensure_ascii=False,
        )

    if _tool_in_skill_scope("retrieve", scoped):
        reg.register(
            "retrieve",
            description="按查询文本检索知识库，返回 path/snippet/score 列表（JSON 数组字符串）。",
            parameters=RETRIEVE_PARAMETERS,
            handler=_retrieve,
        )
    if _tool_in_skill_scope("read_ksfs", scoped):
        reg.register(
            "read_ksfs",
            description="只读打开 KSFS 根（paths.ksfs_root）下的相对路径 Markdown/文本（禁止绝对路径与 ..）。",
            parameters=READ_KSFS_PARAMETERS,
            handler=_read_ksfs,
        )
    if _tool_in_skill_scope("list_ksfs", scoped):
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
    if _tool_in_skill_scope("write_draft", scoped):
        reg.register(
            "write_draft",
            description="将完整草稿内容写入 workspace 下的相对路径（禁止写出 workspace 外）。",
            parameters=WRITE_DRAFT_PARAMETERS,
            handler=_write_draft,
        )
    if _tool_in_skill_scope("list_drafts", scoped):
        reg.register(
            "list_drafts",
            description="列出 workspace 根下某目录中的草稿（仅 .md/.txt 与目录名；排除 conversations/ 与 README.md）。",
            parameters=LIST_DRAFTS_PARAMETERS,
            handler=_list_drafts,
        )
    if _tool_in_skill_scope("read_draft", scoped):
        reg.register(
            "read_draft",
            description="只读打开 workspace 根下的相对路径草稿（禁止绝对路径与 ..）。",
            parameters=READ_DRAFT_PARAMETERS,
            handler=_read_draft,
        )
    if _tool_in_skill_scope("promote_draft", scoped):
        reg.register(
            "promote_draft",
            description="将 workspace 下的草稿晋升至 KSFS（复制后触发 HSI 同步）。调用前请确认用户已审阅同意。",
            parameters=PROMOTE_DRAFT_PARAMETERS,
            handler=_promote_draft,
        )
    for t, cmd, child_env in mcp_handlers:
        if not _tool_in_skill_scope(t.name, scoped):
            continue
        params: dict[str, Any]
        if isinstance(t.inputSchema, dict):
            params = t.inputSchema
        else:
            params = {"type": "object", "properties": {}}
        reg.register(
            t.name,
            description=t.description or f"MCP 工具 {t.name}",
            parameters=params,
            handler=make_stdio_mcp_tool_handler(cmd, child_env, t.name, cwd=repo),
        )
    return reg
