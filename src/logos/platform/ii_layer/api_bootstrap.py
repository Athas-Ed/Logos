"""V0.2 契约路由：健康检查 + 启动配置（``GET /api/v1/health``, ``GET /api/v1/bootstrap``）。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal, cast

import httpx
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
    custom_page: str | None = None


class BootstrapResponse(BaseModel):
    default_presentation: Literal["work", "developer"]
    log_profile: Literal["minimal", "standard", "verbose", "audit"]
    operating_mode: str
    llm_mode: Literal["stub", "remote"]
    # 若 llm_mode 为 "remote" 但实际校验失败时，改为 "stub" 并在此填入错误信息
    llm_error: str = ""
    obs_show_log_root_in_gui: bool = False
    obs_logs_root: str | None = None
    #: 解析后的档 B 会话目录绝对路径（``paths.CONVERSATIONS_CACHE``）
    conversations_cache_root: str
    ui: BootstrapUiPayload
    skills: list[BootstrapSkillPayload] = Field(default_factory=list)


# ── 启动时 API Key 校验（轻量、自包含，不依赖 api_config.py 的复杂 httpx 设置）──

#: 进程级缓存：已验证过的 (provider, base_url, key) 三元组；避免多次调用 bootstrap 时重复请求 LLM API。
_CACHED_KEY_VALID: tuple[str, str, str, bool, str] | None = None


def _bootstrap_validate_key(
    api_key: str, base_url: str, provider: str
) -> tuple[bool, str]:
    """用最简配置校验 API Key（``verify=False`` 避免 Docker 内 CA 问题）。

    结果缓存于进程级变量：相同 (provider, base_url, api_key) 组合仅首次实际请求。
    """
    global _CACHED_KEY_VALID
    key = api_key.strip()
    if not key:
        return False, "API Key 为空"

    # 缓存命中：同一三元组直接返回上次结果
    if _CACHED_KEY_VALID is not None:
        cp, cb, ck, cv, ce = _CACHED_KEY_VALID
        if cp == provider and cb == base_url.rstrip("/") and ck == key:
            return cv, ce

    if provider == "anthropic":
        # Anthropic：POST /v1/messages（max_tokens=1 最小消耗）
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                result: tuple[bool, str] = (True, "")
            elif resp.status_code in (401, 403):
                result = (False, f"API Key 无效（{resp.status_code}）")
            elif resp.status_code == 400:
                # 模型名不对但 Key 有效
                result = (True, "")
            else:
                result = (False, f"验证失败（HTTP {resp.status_code}）")
        except httpx.ConnectError:
            result = (False, f"无法连接到 {base_url}")
        except Exception as exc:
            result = (False, f"验证异常：{exc}")
    else:
        # OpenAI / DeepSeek / Custom：GET /v1/models
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                result = (True, "")
            elif resp.status_code == 401:
                result = (False, "API Key 无效（401 Unauthorized）")
            elif resp.status_code == 403:
                result = (False, "API Key 无权限（403 Forbidden）")
            else:
                result = (False, f"验证失败（HTTP {resp.status_code}）")
        except httpx.ConnectError:
            result = (False, f"无法连接到 {base_url}")
        except httpx.TimeoutException:
            result = (False, "连接超时")
        except Exception as exc:
            result = (False, f"验证异常：{exc}")

    # 写入缓存后再返回
    _CACHED_KEY_VALID = (provider, base_url.rstrip("/"), key, result[0], result[1])
    return result


def build_bootstrap_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/health")
    def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/llm-diag")
    def llm_diag_v1(ports: AppPortsDep) -> dict[str, str]:
        """诊断：查看 LLM 配置状态和验证结果。"""
        key = (ports.settings.llm_api_key or "").strip()
        provider = (ports.settings.llm_provider or "").strip().lower()
        base_url = ports.settings.llm_base_url.strip()

        # 模拟验证
        if not key:
            return {"llm_mode": "stub", "llm_error": "api_key 为空", "has_key": "false"}

        result = _bootstrap_validate_key(key, base_url, provider)
        return {
            "llm_mode": "remote" if result[0] else "stub",
            "llm_error": result[1],
            "has_key": "true",
            "provider": provider or "openai",
            "base_url": base_url,
            "key_preview": key[:8] + "..." if len(key) > 8 else key,
        }

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
                    custom_page=s.custom_page,
                )
            )
        repo = resolve_repo_root()
        conv_cache_abs = str(
            resolve_conversations_cache_abs(
                repo, ports.settings.conversations_cache
            )
        )

        # ── 判断 LLM 模式 + 实际校验 API Key ────────────────────────
        llm_mode = _resolve_llm_mode(ports.settings, ports.llm)
        llm_error = ""
        if llm_mode == "remote" and (ports.settings.llm_api_key or "").strip():
            provider = (ports.settings.llm_provider or "").strip().lower()
            key = ports.settings.llm_api_key.strip()
            base_url = ports.settings.llm_base_url.strip()
            _log.info(
                "启动时验证 API Key（provider=%s, base_url=%s）",
                provider or "openai",
                base_url,
            )
            try:
                valid, err_msg = _bootstrap_validate_key(key, base_url, provider)
                if not valid:
                    llm_mode = "stub"
                    llm_error = err_msg or "API Key 无效"
                    _log.warning("API Key 验证失败: %s", llm_error)
                else:
                    _log.info("API Key 验证成功")
            except Exception as exc:
                _log.error("API Key 验证过程异常: %s", exc)
                llm_mode = "stub"
                llm_error = f"验证异常：{exc}"

        return BootstrapResponse(
            default_presentation=pres,
            log_profile=cast(
                Literal["minimal", "standard", "verbose", "audit"], prof
            ),
            operating_mode=ports.settings.operating_mode,
            llm_mode=llm_mode,
            llm_error=llm_error,
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
