"""V0.2 契约路由聚合器。

Router 聚合入口：``build_v1_router()`` 被 ``app.py`` 调用，各子模块在函数内延迟导入以避免循环依赖。

共享工具函数（跨子模块使用）保留在此模块。

拆分模块：
- ``api_bootstrap.py`` — ``GET /api/v1/health``, ``GET /api/v1/bootstrap``
- ``api_chat.py`` — ``POST /api/v1/chat``（SSE）
- ``api_developer.py`` — ``GET /api/v1/developer/*``
- ``api_review.py`` — ``GET/POST /api/v1/drafts/*``, ``POST /api/v1/setting-entry/promote``

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

_log = logging.getLogger("logos.api.v1")


# ═══════════════════════════════════════════════════════════════════
# 共享工具函数
# ═══════════════════════════════════════════════════════════════════


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    # 紧凑 JSON：减少 SSE 带宽与 ``json.dumps`` 少量开销（S13 小步优化）
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event}\ndata: {body}\n\n"


def _effective_presentation(raw: str | None, default: str) -> Literal["work", "developer"]:
    if raw is None or not str(raw).strip():
        base = default
    else:
        base = str(raw).strip().lower()
    if base in ("developer", "dev"):
        return "developer"
    return "work"


def _resolve_llm_mode(settings: Any) -> Literal["stub", "remote"]:
    if os.environ.get("LOGOS_FORCE_STUB_LLM", "").strip() == "1":
        return "stub"
    if not (settings.llm_api_key or "").strip():
        return "stub"
    return "remote"


def _resolve_workspace_root(settings: Any) -> Path:
    from logos.platform.mcp_stdio import resolve_repo_root

    p = Path(settings.workspace_root)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


def _resolve_ksfs_root(settings: Any) -> Path:
    from logos.platform.mcp_stdio import resolve_repo_root

    p = Path(settings.ksfs_root)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


def _resolve_hsi_db(settings: Any) -> Path:
    from logos.platform.mcp_stdio import resolve_repo_root

    p = Path(settings.hsi_sqlite_path)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


# ═══════════════════════════════════════════════════════════════════
# Router 聚合
# ═══════════════════════════════════════════════════════════════════


def build_v1_router() -> Any:
    from fastapi import APIRouter

    # 延迟导入避免循环依赖（子模块 import .api_v1 时本模块已完全加载）
    from .api_bootstrap import build_bootstrap_router
    from .api_chat import build_chat_router
    from .api_developer import build_developer_router
    from .api_review import build_review_router

    router = APIRouter(prefix="/api/v1", tags=["api-v1"])
    router.include_router(build_bootstrap_router())
    router.include_router(build_chat_router())
    router.include_router(build_developer_router())
    router.include_router(build_review_router())
    return router
