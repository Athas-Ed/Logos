"""V0.2 契约路由：审核晋升专用端点（``GET/POST /api/v1/drafts/*``, ``POST /api/v1/setting-entry/promote``）。

前端直接调用，不走 Agent 工具。ReviewPage 专用。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``、
``original_docs/重要子系统开发文档/审核晋升面板开发文档.md``。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from .deps import AppPortsDep, LLMDep, ResolvedPathsDep

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
    scope: str = "setting_entry"


class DraftsPromoteResponse(BaseModel):
    ok: bool
    applied: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    notes: str = ""


class DraftsDeleteBody(BaseModel):
    paths: list[str]
    scope: str = "setting_entry"


class DraftsDeleteResponse(BaseModel):
    ok: bool
    deleted: list[str] = Field(default_factory=list)


class DraftsWriteBody(BaseModel):
    path: str
    content: str
    scope: str = "setting_entry"


class RewriteFileInput(BaseModel):
    path: str
    content: str


class RewriteRequestBody(BaseModel):
    files: list[RewriteFileInput]
    requirements: str = ""
    system_hint: str = "你是设定审核助手。注意保留 YAML front matter 与正文结构。"
    scope: str = "setting_entry"


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


def _scope_drafts_root(ws_root: Path, settings: Any, scope: str) -> Path:
    """Return the drafts root directory for a *scope* under ``pending_review/<scope>/``.

    ``scope=""`` means the ``pending_review/`` root itself.
    """
    base = ws_root / settings.pending_review_subdir
    return base if not scope else base / scope


def _scope_rel_to_ws_path(ws_root: Path, settings: Any, scope: str, rel: str) -> Path:
    """Convert a *scope*-relative path to a full workspace-relative :class:`Path`."""
    return _scope_drafts_root(ws_root, settings, scope) / rel.replace("\\", "/").lstrip("/")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _append_promotion_log(logs_root: Path, entry: dict[str, Any]) -> None:
    """Append one JSON line to ``logs/promotion/promotions.jsonl``."""
    import json

    log_dir = logs_root / "promotion"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "promotions.jsonl"
    line = json.dumps(entry, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")


def build_review_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/setting-entry/promote")
    def setting_entry_promote_v1(
        body: SettingEntryPromoteBody,
        ports: AppPortsDep,
        paths: ResolvedPathsDep,
    ) -> SettingEntryPromoteResponse:
        """人审后将 setting_entry 草稿复制至 KSFS 并触发 HSI 同步。"""
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        ws_root = paths.workspace_root
        ksfs_root = paths.ksfs_root
        logs_root = paths.logs_root
        drafts_root = _scope_drafts_root(ws_root, ports.settings, "setting_entry")
        hsi_db = paths.hsi_sqlite_path
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
        for app in report.applied:
            _append_promotion_log(logs_root, {
                "ts": _now_iso(),
                "op": "promote",
                "src": app,
                "dst": app,
                "ok": True,
            })
        for sk in report.skipped:
            _append_promotion_log(logs_root, {
                "ts": _now_iso(),
                "op": "promote",
                "src": sk,
                "dst": sk,
                "ok": False,
                "note": report.notes,
            })
        return SettingEntryPromoteResponse(
            ok=report.ok,
            applied=list(report.applied),
            skipped=list(report.skipped),
            notes=report.notes,
        )

    @router.get("/drafts")
    def drafts_list_v1(
        ports: AppPortsDep,
        paths: ResolvedPathsDep,
        scope: str = "setting_entry",
    ) -> DraftsListResponse:
        """列出 pending_review 下某 scope 的全部草稿文件。scope 空 = pending_review 根。"""
        ws_root = paths.workspace_root
        target = _scope_drafts_root(ws_root, ports.settings, scope)

        if not target.is_dir():
            return DraftsListResponse(files=[])

        files: list[dict[str, Any]] = []
        for entry in sorted(target.rglob("*"), key=lambda p: p.name):
            if entry.name.startswith(".") or entry.name == "README.md":
                continue
            if entry.is_file() and entry.suffix.lower() in (".md", ".markdown", ".txt", ".yaml", ".json"):
                st = entry.stat()
                rel = entry.relative_to(target).as_posix()
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
        paths: ResolvedPathsDep,
        path: str,
        scope: str = "setting_entry",
    ) -> DraftsReadResponse:
        """读取 pending_review 下某 scope 内文件的正文。path 相对 scope 根。"""
        ws_root = paths.workspace_root
        full = _scope_rel_to_ws_path(ws_root, ports.settings, scope, path)
        content = full.read_text(encoding="utf-8")
        return DraftsReadResponse(path=path, content=content)

    @router.post("/drafts/promote")
    def drafts_promote_v1(
        body: DraftsPromoteBody,
        ports: AppPortsDep,
        paths: ResolvedPathsDep,
    ) -> DraftsPromoteResponse:
        """将 pending_review/<scope>/ 下的草稿晋升至 KSFS。成功后删除源文件。"""
        from logos.ports.draft_promotion import PromotionItem
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        ws_root = paths.workspace_root
        ksfs_root = paths.ksfs_root
        logs_root = paths.logs_root
        drafts_root = _scope_drafts_root(ws_root, ports.settings, body.scope)
        hsi_db = paths.hsi_sqlite_path
        port = FilesystemDraftPromotionPort(hsi_db=hsi_db)

        applied: list[str] = []
        failed: list[str] = []
        fail_reasons: list[str] = []
        for rel in body.paths:
            src = (drafts_root / rel).resolve()
            try:
                src.relative_to(drafts_root)
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
            report = port.apply_promotion(drafts_root, ksfs_root, candidates)
            if report.ok:
                applied.append(rel)
                _append_promotion_log(logs_root, {
                    "ts": _now_iso(),
                    "op": "promote",
                    "src": rel,
                    "dst": rel,
                    "ok": True,
                })
                try:
                    src.unlink()
                except OSError:
                    pass
            else:
                failed.append(rel)
                fail_reasons.append(f"{rel}: {report.notes}")
                _append_promotion_log(logs_root, {
                    "ts": _now_iso(),
                    "op": "promote",
                    "src": rel,
                    "dst": rel,
                    "ok": False,
                    "note": report.notes,
                })
        notes = (
            f"晋升 {len(applied)} 个，失败 {len(failed)} 个。"
            if failed
            else f"已晋升 {len(applied)} 个文件"
        )
        if fail_reasons:
            notes += "\n" + "\n".join(fail_reasons)
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
        paths: ResolvedPathsDep,
    ) -> DraftsDeleteResponse:
        """删除 pending_review/<scope>/ 下的草稿源文件。path 相对 scope 根。"""
        ws_root = paths.workspace_root
        drafts_root = _scope_drafts_root(ws_root, ports.settings, body.scope)
        deleted: list[str] = []
        for rel in body.paths:
            target = (drafts_root / rel).resolve()
            try:
                target.relative_to(drafts_root)
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
        paths: ResolvedPathsDep,
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

        ws_root = paths.workspace_root
        drafts_root = _scope_drafts_root(ws_root, ports.settings, body.scope)
        written: list[str] = []
        failed: list[str] = []
        for entry in results:
            rpath = (entry.get("path") or "").strip()
            rcontent = entry.get("content") or ""
            if not rpath:
                continue
            try:
                target = (drafts_root / rpath).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rcontent, encoding="utf-8")
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
        paths: ResolvedPathsDep,
    ) -> dict[str, Any]:
        """覆写 pending_review/<scope>/ 下的草稿文件。path 相对 scope 根。"""
        ws_root = paths.workspace_root
        drafts_root = _scope_drafts_root(ws_root, ports.settings, body.scope)
        target = (drafts_root / body.path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content, encoding="utf-8")
        return {"ok": True, "path": body.path, "result": "written"}

    return router
