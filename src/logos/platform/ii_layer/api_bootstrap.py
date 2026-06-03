"""V0.2 契约路由：健康检查 + 启动配置（``GET /api/v1/health``, ``GET /api/v1/bootstrap``）。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from .api_v1 import _effective_presentation, _resolve_llm_mode
from .deps import AppPortsDep

_log = logging.getLogger("logos.api.bootstrap")


class BootstrapUiPayload(BaseModel):
    SSE_maxNum: int
    cache_warn_bytes: int
    max_history_full_text: int
    react_max_steps: int
    react_max_qa_steps: int


class BootstrapSkillPayload(BaseModel):
    """产品 Skill 摘要，供 GUI 技能面板（F5-08）。"""

    skill_id: str
    display_name: str
    description: str
    ui_instructions: str = ""
    persistence_tier: Literal["p0", "p1", "p2"]
    paradigm: Literal["dialogue", "react", "plan", "pipeline"]
    turn_policy: Literal["single", "multi"] = "single"
    qa_mode: Literal["normal", "continuous"] = "normal"
    panel_visible: bool = True


class BootstrapResponse(BaseModel):
    default_presentation: Literal["work", "developer"]
    log_profile: Literal["minimal", "standard", "verbose", "audit"]
    operating_mode: str
    llm_mode: Literal["stub", "remote"]
    obs_show_log_root_in_gui: bool = False
    obs_logs_root: str | None = None
    #: 解析后的档 B 会话目录绝对路径（``paths.CONVERSATIONS_CACHE``）
    conversations_cache_root: str
    ui: BootstrapUiPayload
    skills: list[BootstrapSkillPayload] = Field(default_factory=list)


def build_bootstrap_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/health")
    def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/bootstrap")
    def bootstrap_v1(ports: AppPortsDep) -> BootstrapResponse:
        from logos.platform.config.paths_resolve import resolve_conversations_cache_abs
        from logos.platform.mcp_stdio import resolve_repo_root
        from logos.platform.skills_config import resolve_skill_config
        from logos.platform.skills_registry import get_skill_manifest, list_bootstrap_skill_summaries

        pres = _effective_presentation(None, ports.settings.ui_default_presentation)
        prof = str(ports.settings.obs_log_profile or "standard").strip().lower()
        if prof not in ("minimal", "standard", "verbose", "audit"):
            prof = "standard"
        show_root = bool(ports.settings.obs_show_log_root_in_gui)
        logs_abs: str | None = None
        if show_root:
            logs_abs = str(Path(ports.settings.logs_root).expanduser().resolve())
        skill_payloads = []
        for s in list_bootstrap_skill_summaries():
            manifest = get_skill_manifest(s.skill_id)
            cfg = resolve_skill_config(s.skill_id, manifest, ports.settings)
            skill_payloads.append(
                BootstrapSkillPayload(
                    skill_id=s.skill_id,
                    display_name=s.display_name,
                    description=s.description,
                    ui_instructions=s.ui_instructions,
                    persistence_tier=s.persistence_tier,
                    paradigm=s.paradigm,
                    turn_policy=s.turn_policy,
                    qa_mode=cfg.get("qa_mode", "normal"),
                    panel_visible=s.panel_visible,
                )
            )
        repo = resolve_repo_root()
        conv_cache_abs = str(
            resolve_conversations_cache_abs(
                repo, ports.settings.conversations_cache
            )
        )
        return BootstrapResponse(
            default_presentation=pres,
            log_profile=cast(
                Literal["minimal", "standard", "verbose", "audit"], prof
            ),
            operating_mode=ports.settings.operating_mode,
            llm_mode=_resolve_llm_mode(ports.settings),
            obs_show_log_root_in_gui=show_root,
            obs_logs_root=logs_abs,
            conversations_cache_root=conv_cache_abs,
            ui=BootstrapUiPayload(
                SSE_maxNum=ports.settings.ui_sse_max_num,
                cache_warn_bytes=ports.settings.ui_cache_warn_bytes,
                max_history_full_text=ports.settings.ui_max_history_full_text,
                react_max_steps=ports.settings.react_max_steps,
                react_max_qa_steps=ports.settings.react_max_qa_steps,
            ),
            skills=skill_payloads,
        )

    return router
