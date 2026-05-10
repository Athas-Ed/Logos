"""LLM 具体实现（OpenAI 兼容 HTTP）。"""

from __future__ import annotations

from logos.ports import AppSettings

from logos.infrastructure.llm.openai_compatible import OpenAICompatibleChatClient

__all__ = ["OpenAICompatibleChatClient", "build_chat_llm_from_settings"]


def build_chat_llm_from_settings(
    settings: AppSettings,
) -> OpenAICompatibleChatClient | None:
    """若配置了 ``llm_api_key`` 则返回客户端，否则返回 ``None``（由调用方使用桩）。"""
    key = (settings.llm_api_key or "").strip()
    if not key:
        return None
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
