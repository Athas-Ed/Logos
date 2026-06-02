"""V0.2 契约路由：审核晋升专用端点（``GET/POST /api/v1/drafts/*``, ``POST /api/v1/setting-entry/promote``）。

前端直接调用，不走 Agent 工具。ReviewPage 专用。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``、
``original_docs/重要子系统开发文档/审核晋升面板开发文档.md``。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from .api_v1 import _resolve_hsi_db, _resolve_ksfs_root, _resolve_workspace_root
from .deps import AppPortsDep, LLMDep

_log = logging.getLogger("logos.api.review")


class SettingEntryPromoteBody(BaseModel):
    """将 ``workspace/setting_entry/`` 下草稿晋升至 KSFS（F6-08）。"""

    draft_relpaths: list[str] | None = Field(
        default=None,
        description="相对 setting_entry 根的路径；省略则晋升全部候选",
    )


class SettingEntryPromoteResponse(BaseModel):
    ok: bool
    applied: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    notes: str = ""


class DraftsListResponse(BaseModel):
    files: list[dict[str, Any]] = Field(default_factory=list)


class DraftsReadResponse(BaseModel):
    path: str
    content: str = ""


class DraftsPromoteBody(BaseModel):
    paths: list[str]


class DraftsPromoteResponse(BaseModel):
    ok: bool
    applied: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    notes: str = ""


class DraftsDeleteBody(BaseModel):
    paths: list[str]


class DraftsDeleteResponse(BaseModel):
    ok: bool
    deleted: list[str] = Field(default_factory=list)


class DraftsWriteBody(BaseModel):
    path: str
    content: str


class RewriteFileInput(BaseModel):
    path: str
    content: str


class RewriteRequestBody(BaseModel):
    files: list[RewriteFileInput]
    requirements: str = ""
    system_hint: str = "你是设定审核助手。注意保留 YAML front matter 与正文结构。"


class RewriteResponse(BaseModel):
    ok: bool
    written: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


def _build_rewrite_prompt(
    files: list[RewriteFileInput],
    requirements: str,
    system_hint: str,
) -> str:
    """构造 LLM prompt，要求以 JSON 格式返回每个文件的新内容。"""
    file_sections = "\n\n".join(
        f"路径：{f.path}\n当前内容：\n{f.content}" for f in files
    )
    req = requirements.strip() or "请根据文件内容进行合理的修订和优化。"
    prompt = f"""你是一位设定审核助手。

用户要求对以下文件进行修订。请以 JSON 格式返回每个文件的新内容。

要求：{req}

系统提示：{system_hint}

需要重写的文件：
---
{file_sections}
---

请严格按照以下 JSON 格式返回，不要包含其他文本：
{{"files":[{{"path":"<路径>","content":"<新内容>"}}]}}
"""
    return prompt


def build_review_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/setting-entry/promote")
    def setting_entry_promote_v1(
        body: SettingEntryPromoteBody,
        ports: AppPortsDep,
    ) -> SettingEntryPromoteResponse:
        """人审后将 setting_entry 草稿复制至 KSFS 并触发 HSI 同步。"""
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        ws_root = _resolve_workspace_root(ports.settings)
        ksfs_root = _resolve_ksfs_root(ports.settings)
        drafts_root = (
            ws_root
            / ports.settings.pending_review_subdir
            / ports.settings.setting_entry_subdir
        )
        hsi_db = _resolve_hsi_db(ports.settings)
        port = FilesystemDraftPromotionPort(hsi_db=hsi_db)
        candidates = port.list_promotion_candidates(drafts_root, ksfs_root)
        if body.draft_relpaths is not None:
            allowed = {p.strip().replace("\\", "/") for p in body.draft_relpaths if p.strip()}
            candidates = [c for c in candidates if c.draft_relpath in allowed]
        if not candidates:
            return SettingEntryPromoteResponse(
                ok=True,
                applied=[],
                skipped=[],
                notes="无匹配的可晋升草稿",
            )
        report = port.apply_promotion(drafts_root, ksfs_root, candidates)
        return SettingEntryPromoteResponse(
            ok=report.ok,
            applied=list(report.applied),
            skipped=list(report.skipped),
            notes=report.notes,
        )

    @router.get("/drafts")
    def drafts_list_v1(
        ports: AppPortsDep,
        dir: str = "",
    ) -> DraftsListResponse:
        """列出 pending_review 下某子目录的全部草稿文件。dir 空 = pending_review 根。"""
        import os

        ws_root = _resolve_workspace_root(ports.settings)
        pending_root = ws_root / ports.settings.pending_review_subdir
        target = pending_root
        raw_dir = (dir or "").strip().replace("\\", "/")
        if raw_dir:
            from logos.platform.sg_layer.path_sandbox import resolve_path_under_root

            try:
                target = resolve_path_under_root(pending_root, raw_dir)
            except ValueError as exc:
                return DraftsListResponse(files=[{"error": str(exc)}])

        if not target.is_dir():
            return DraftsListResponse(files=[])

        files: list[dict[str, Any]] = []
        for entry in sorted(target.iterdir(), key=lambda p: p.name):
            if entry.name.startswith(".") or entry.name == "README.md":
                continue
            if entry.is_file() and entry.suffix.lower() in (".md", ".markdown", ".txt", ".yaml", ".json"):
                st = entry.stat()
                rel = entry.resolve().relative_to(ws_root.resolve()).as_posix()
                files.append({
                    "name": entry.name,
                    "path": rel,
                    "size_bytes": st.st_size,
                    "mtime_ns": st.st_mtime_ns,
                })
        return DraftsListResponse(files=files)

    @router.get("/drafts/read")
    def drafts_read_v1(
        ports: AppPortsDep,
        path: str,
    ) -> DraftsReadResponse:
        """读取 pending_review 下某文件的正文。"""
        ws_root = _resolve_workspace_root(ports.settings)
        pending_root = ws_root / ports.settings.pending_review_subdir
        from logos.platform.sg_layer.path_sandbox import read_text_under_root

        content = read_text_under_root(
            pending_root,
            path,
            context_label="pending_review",
            denied_operation="drafts/read",
        )
        return DraftsReadResponse(path=path, content=content)

    @router.post("/drafts/promote")
    def drafts_promote_v1(
        body: DraftsPromoteBody,
        ports: AppPortsDep,
    ) -> DraftsPromoteResponse:
        """将 pending_review 下的草稿晋升至 KSFS。成功后删除源文件。"""
        from logos.ports.draft_promotion import PromotionItem
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        ws_root = _resolve_workspace_root(ports.settings)
        ksfs_root = _resolve_ksfs_root(ports.settings)
        hsi_db = _resolve_hsi_db(ports.settings)
        port = FilesystemDraftPromotionPort(hsi_db=hsi_db)

        applied: list[str] = []
        failed: list[str] = []
        for rel in body.paths:
            src = (ws_root / rel).resolve()
            try:
                src.relative_to(ws_root)
            except ValueError:
                failed.append(rel)
                continue
            if not src.is_file():
                failed.append(rel)
                continue
            st = src.stat()
            candidates = [
                PromotionItem(
                    draft_relpath=rel,
                    proposed_ksfs_relpath=rel,
                    draft_mtime_ns=st.st_mtime_ns,
                )
            ]
            report = port.apply_promotion(ws_root, ksfs_root, candidates)
            if report.ok:
                applied.append(rel)
                try:
                    src.unlink()
                except OSError:
                    pass
            else:
                failed.append(rel)
        notes = (
            f"晋升 {len(applied)} 个，失败 {len(failed)} 个"
            if failed
            else f"已晋升 {len(applied)} 个文件"
        )
        return DraftsPromoteResponse(
            ok=len(failed) == 0,
            applied=applied,
            failed=failed,
            notes=notes,
        )

    @router.post("/drafts/delete")
    def drafts_delete_v1(
        body: DraftsDeleteBody,
        ports: AppPortsDep,
    ) -> DraftsDeleteResponse:
        """删除 pending_review 下的草稿源文件（晋升成功后清理用）。"""
        ws_root = _resolve_workspace_root(ports.settings)
        deleted: list[str] = []
        for rel in body.paths:
            target = (ws_root / rel).resolve()
            try:
                target.relative_to(ws_root)
            except ValueError:
                continue
            if target.is_file():
                try:
                    target.unlink()
                    deleted.append(rel)
                except OSError:
                    pass
        return DraftsDeleteResponse(ok=len(deleted) == len(body.paths), deleted=deleted)

    @router.post("/drafts/rewrite")
    def drafts_rewrite_v1(
        body: RewriteRequestBody,
        ports: AppPortsDep,
        llm: LLMDep,
    ) -> RewriteResponse:
        """批量重写草稿：前端传入文件原文 + 要求，服务端调 LLM JSON mode 后直接写入文件。"""
        from logos.ports.llm import ChatMessage

        if not body.files:
            return RewriteResponse(ok=True, written=[], failed=[])

        prompt = _build_rewrite_prompt(body.files, body.requirements, body.system_hint)
        system_msg = "你是设定审核助手。请严格按照用户要求的 JSON 格式返回，不要包含 markdown 代码块或其他解释。"

        try:
            raw = llm.complete(
                [ChatMessage(role="system", content=system_msg), ChatMessage(role="user", content=prompt)],
                json_mode=True,
            )
        except Exception as exc:
            _log.exception("drafts/rewrite LLM 调用异常")
            return RewriteResponse(
                ok=False,
                written=[],
                failed=[f.path for f in body.files],
            )

        # 解析 JSON 响应
        import json

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            _log.warning("drafts/rewrite LLM 返回非 JSON: %r", raw[:200])
            return RewriteResponse(
                ok=False,
                written=[],
                failed=[f.path for f in body.files],
            )

        results = parsed if isinstance(parsed, list) else parsed.get("files", [])
        if not isinstance(results, list):
            results = []

        written: list[str] = []
        failed: list[str] = []
        for entry in results:
            rpath = (entry.get("path") or "").strip()
            rcontent = entry.get("content") or ""
            if not rpath:
                continue
            try:
                from logos.platform.sg_layer.path_sandbox import write_draft_under_workspace

                write_draft_under_workspace(
                    _resolve_workspace_root(ports.settings),
                    rpath,
                    rcontent,
                )
                written.append(rpath)
            except Exception as exc:
                _log.warning("drafts/rewrite 写入 %r 失败: %s", rpath, exc)
                failed.append(rpath)

        return RewriteResponse(
            ok=len(failed) == 0,
            written=written,
            failed=failed,
        )

    @router.post("/drafts/write")
    def drafts_write_v1(
        body: DraftsWriteBody,
        ports: AppPortsDep,
    ) -> dict[str, Any]:
        """覆写 pending_review 下的草稿文件（LLM 打回重写后写入）。"""
        from logos.platform.sg_layer.path_sandbox import write_draft_under_workspace

        result = write_draft_under_workspace(
            _resolve_workspace_root(ports.settings),
            body.path,
            body.content,
        )
        return {"ok": True, "path": body.path, "result": result}

    return router
