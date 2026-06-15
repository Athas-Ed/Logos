"""V0.2+ 契约路由：运行时配置管理（``POST /api/v1/config/llm-api-key``）。

允许用户在 UI 中输入 LLM API Key，后端写入 ``config/local.yaml``
并热替换 LLM 实现，即时生效（无需重启容器）。

支持的提供商：
- ``openai`` — OpenAI（ChatGPT/GPT-4 等）
- ``deepseek`` — DeepSeek（DeepSeek-V3/R1 等）
- ``anthropic`` — Anthropic Claude
- ``custom`` — 自托管 OpenAI 兼容端点（Ollama/vLLM 等）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from pydantic import BaseModel

from .deps import AppPortsDep
from .llm_ref import LLMRef

_log = logging.getLogger("logos.api.config")

_REQUEST_TIMEOUT_SECS = 10

LlmProvider = Literal["openai", "deepseek", "anthropic", "custom"]


class LlmApiKeyBody(BaseModel):
    """前端提交的 LLM 凭证。"""

    api_key: str
    provider: LlmProvider = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


class LlmApiKeyResponse(BaseModel):
    success: bool
    llm_mode: str  # "stub" | "remote"（更新后的状态）
    detail: str = ""


# ── 各提供商默认值 ──────────────────────────────────────────────────

PROVIDER_DEFAULTS: dict[LlmProvider, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
    },
    "custom": {
        "base_url": "",
        "model": "",
    },
}


# ── 校验函数 ────────────────────────────────────────────────────────


def _validate_api_key(
    api_key: str, base_url: str, provider: LlmProvider,
) -> tuple[bool, str]:
    """按提供商策略校验 API Key 有效性。返回 (是否有效, 错误信息)。

    统一使用 ``verify=False`` 避免系统 CA 文件缺失导致的 FileNotFoundError。
    实际 LLM 调用使用 ``OpenAICompatibleChatClient`` 中的完整 SSL 配置。
    """

    # --- Anthropic：调用 /v1/messages 校验 ---
    if provider == "anthropic":
        from logos.infrastructure.llm.anthropic import validate_anthropic_api_key

        return validate_anthropic_api_key(api_key, base_url)

    # --- OpenAI / DeepSeek / Custom（统一走 OpenAI 兼容校验） ---
    base = base_url.rstrip("/")
    models_url = f"{base}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = httpx.get(
            models_url,
            headers=headers,
            timeout=_REQUEST_TIMEOUT_SECS,
            verify=False,
        )
        if resp.status_code == 200:
            return True, ""
        if resp.status_code == 401:
            return False, "API Key 无效（401 Unauthorized）"
        if resp.status_code == 403:
            return False, "API Key 无权限（403 Forbidden）"
        if resp.status_code == 404:
            return (
                False,
                f"服务端不存在 /v1/models 端点（404），请确认 base_url 是否正确。"
                f"当前值：{base}",
            )
        return (
            False,
            f"验证失败（HTTP {resp.status_code}）：{resp.text[:200]}",
        )
    except httpx.ConnectError:
        return False, f"无法连接到 {base}，请检查 base_url 是否正确"
    except httpx.TimeoutException:
        return False, f"连接 {base} 超时（{_REQUEST_TIMEOUT_SECS}s）"
    except Exception as exc:
        return False, f"验证异常：{exc}"


# ── 配置持久化 ──────────────────────────────────────────────────────


def _write_llm_config(
    config_dir: Path,
    api_key: str,
    base_url: str,
    model: str,
    provider: str = "",
    max_tokens: int = 4096,
) -> None:
    """将 LLM 凭证写入 ``config/local.yaml``（保留已有键值）。"""
    local_path = config_dir / "local.yaml"
    existing: dict[str, Any] = {}
    if local_path.is_file():
        raw = yaml.safe_load(local_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            existing = raw
    existing.setdefault("llm", {})
    existing["llm"]["api_key"] = api_key
    existing["llm"]["base_url"] = base_url
    existing["llm"]["model"] = model
    if provider:
        existing["llm"]["provider"] = provider
    existing["llm"]["max_tokens"] = max_tokens
    local_path.write_text(
        yaml.dump(existing, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def _resolve_config_dir(settings: Any) -> Path:
    """从当前环境推断 config 目录路径。"""
    import os

    env_dir = os.environ.get("LOGOS_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    from logos.platform.mcp_stdio import resolve_repo_root

    return resolve_repo_root() / "config"


# ── 路由 ────────────────────────────────────────────────────────────


def build_config_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/config/llm-api-key")
    def config_set_llm_api_key(
        body: LlmApiKeyBody,
        ports: AppPortsDep,
    ) -> LlmApiKeyResponse:
        key = (body.api_key or "").strip()
        if not key:
            return LlmApiKeyResponse(
                success=False,
                llm_mode="stub",
                detail="API Key 不能为空",
            )

        # 1. 校验 API Key
        valid, err_msg = _validate_api_key(key, body.base_url, body.provider)
        if not valid:
            return LlmApiKeyResponse(
                success=False,
                llm_mode="stub",
                detail=err_msg,
            )

        # 2. 持久化到 config/local.yaml
        config_dir = _resolve_config_dir(ports.settings)
        try:
            _write_llm_config(
                config_dir,
                key,
                body.base_url,
                body.model,
                provider=body.provider,
                max_tokens=ports.settings.llm_max_tokens,
            )
        except OSError as exc:
            _log.error("写入 config/local.yaml 失败: %s", exc)
            return LlmApiKeyResponse(
                success=False,
                llm_mode="stub",
                detail=f"无法写入配置文件: {exc}",
            )

        # 3. 按 provider 构建并热替换 LLM
        from logos.infrastructure.llm import (
            AnthropicChatClient,
            OpenAICompatibleChatClient,
        )

        if body.provider == "anthropic":
            new_llm = AnthropicChatClient(
                api_key=key,
                base_url=body.base_url,
                model=body.model,
                max_tokens=ports.settings.llm_max_tokens,
                verify_ssl=ports.settings.llm_verify_ssl,
                ca_bundle=ports.settings.llm_ca_bundle,
                http_proxy=ports.settings.llm_http_proxy,
                https_proxy=ports.settings.llm_https_proxy,
                no_proxy=ports.settings.llm_no_proxy,
            )
        else:
            new_llm = OpenAICompatibleChatClient(
                api_key=key,
                base_url=body.base_url,
                model=body.model,
                verify_ssl=ports.settings.llm_verify_ssl,
                ca_bundle=ports.settings.llm_ca_bundle,
                http_proxy=ports.settings.llm_http_proxy,
                https_proxy=ports.settings.llm_https_proxy,
                no_proxy=ports.settings.llm_no_proxy,
            )
        if isinstance(ports.llm, LLMRef):
            ports.llm.swap(new_llm)

        _log.info(
            "LLM API Key 已更新（via GUI）: provider=%s, base_url=%s, model=%s",
            body.provider,
            body.base_url,
            body.model,
        )

        # 4. 返回更新后的状态
        return LlmApiKeyResponse(
            success=True,
            llm_mode="remote",
            detail="LLM 配置已更新，可使用完整功能",
        )

    return router
