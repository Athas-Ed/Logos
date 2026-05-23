"""OpenAI 兼容 LLM 客户端（单测，不访问外网）。"""

from __future__ import annotations

import json

import httpx
import pytest

from logos.platform.config import merged_dict_to_app_settings
from logos.infrastructure.llm import OpenAICompatibleChatClient, build_chat_llm_from_settings
from logos.ports.llm import ChatMessage


def test_openai_compatible_stream_parses_sse_deltas() -> None:
    stream_body = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
        "data: [DONE]\n\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body.get("stream") is True
        assert body["messages"][0] == {"role": "user", "content": "hi"}
        return httpx.Response(
            200,
            content=stream_body,
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )

    client = OpenAICompatibleChatClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
    )
    parts = list(client.stream_completion([ChatMessage(role="user", content="hi")]))
    assert "".join(parts) == "你好"


def test_openai_compatible_complete_parses_choice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content.decode())
        assert body["model"] == "deepseek-chat"
        assert body["messages"][0] == {"role": "user", "content": "hi"}
        assert "response_format" not in body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "你好"}}]},
        )

    client = OpenAICompatibleChatClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
    )
    out = client.complete([ChatMessage(role="user", content="hi")])
    assert out == "你好"


def test_openai_compatible_json_mode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body.get("response_format") == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    client = OpenAICompatibleChatClient(
        api_key="k",
        base_url="https://x/v1",
        model="m",
        transport=httpx.MockTransport(handler),
    )
    assert client.complete([], json_mode=True) == "{}"


def test_build_chat_llm_from_settings_none_without_key() -> None:
    s = merged_dict_to_app_settings({})
    assert build_chat_llm_from_settings(s) is None


def test_build_chat_llm_from_settings_with_key() -> None:
    s = merged_dict_to_app_settings({"llm": {"api_key": "sk-x", "model": "m"}})
    c = build_chat_llm_from_settings(s)
    assert c is not None


def test_openai_compatible_http_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = OpenAICompatibleChatClient(
        api_key="k",
        base_url="https://x/v1",
        model="m",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RuntimeError, match="500"):
        client.complete([ChatMessage(role="user", content="x")])
