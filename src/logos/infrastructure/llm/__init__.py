"""LLM 具体实现（OpenAI 兼容 HTTP / Anthropic）。"""

from __future__ import annotations

from logos.ports import AppSettings

from logos.infrastructure.llm.openai_compatible import OpenAICompatibleChatClient
from logos.infrastructure.llm.anthropic import AnthropicChatClient

__all__ = [
    "OpenAICompatibleChatClient",
    "AnthropicChatClient",
    "build_chat_llm_from_settings",
]


def build_chat_llm_from_settings(
    settings: AppSettings,
) -> OpenAICompatibleChatClient | AnthropicChatClient | None:
    """若配置了 ``llm_api_key`` 则按 ``llm_provider`` 路由到对应客户端，否则返回 ``None``。"""
    key = (settings.llm_api_key or "").strip()
    if not key:
        return None

    provider = (settings.llm_provider or "").strip().lower()

    if provider == "anthropic":
        return AnthropicChatClient(
            api_key=key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            verify_ssl=settings.llm_verify_ssl,
            ca_bundle=settings.llm_ca_bundle,
            http_proxy=settings.llm_http_proxy,
            https_proxy=settings.llm_https_proxy,
            no_proxy=settings.llm_no_proxy,
        )

    # openai / deepseek / custom / 默认 → OpenAI 兼容
    return OpenAICompatibleChatClient(
        api_key=key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        verify_ssl=settings.llm_verify_ssl,
        ca_bundle=settings.llm_ca_bundle,
        http_proxy=settings.llm_http_proxy,
        https_proxy=settings.llm_https_proxy,
        no_proxy=settings.llm_no_proxy,
    )
