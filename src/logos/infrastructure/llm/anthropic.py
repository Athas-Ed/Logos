"""Anthropic Claude ``/v1/messages`` 客户端。

与 OpenAI 兼容协议的关键差异：
- 端点：``POST {base_url}/v1/messages``
- 认证：``x-api-key`` 请求头（非 ``Authorization: Bearer``）
- 必需请求头：``anthropic-version: 2023-06-01``
- 系统提示在顶层 ``system`` 字段而非 messages 数组
- ``max_tokens`` 为必填字段
- 流式事件名不同（``content_block_delta`` 等）
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from logos.ports.llm import ChatMessage

_log = logging.getLogger("logos.infrastructure.llm.anthropic")

_ANTHROPIC_VERSION = "2023-06-01"
_REQUEST_TIMEOUT_SECS = 120
_STREAM_TIMEOUT_SECS = 300

# 默认 max_tokens（Anthropic API 必填）
_DEFAULT_MAX_TOKENS = 4096


class AnthropicChatClient:
    """同步调用 ``POST {base_url}/v1/messages``，实现 :class:`~logos.ports.llm.LLMClient` 协议。"""

    __slots__ = (
        "_api_key",
        "_base",
        "_model",
        "_max_tokens",
        "_timeout",
        "_stream_timeout",
        "_verify",
        "_proxies",
        "_trust_env",
    )

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        timeout: float = _REQUEST_TIMEOUT_SECS,
        stream_timeout: float = _STREAM_TIMEOUT_SECS,
        verify_ssl: bool = True,
        ca_bundle: str = "",
        http_proxy: str = "",
        https_proxy: str = "",
        no_proxy: str = "",
    ) -> None:
        self._api_key = api_key.strip()
        self._base = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._stream_timeout = stream_timeout

        np = no_proxy.strip()
        if np:
            os.environ["NO_PROXY"] = np
            _log.debug("Anthropic 客户端设置 NO_PROXY=%s", np)

        if not verify_ssl:
            self._verify: bool | str = False
        elif ca_bundle.strip():
            p = Path(ca_bundle.strip()).expanduser()
            self._verify = str(p.resolve(strict=False))
        else:
            self._verify = True

        hp, hsp = http_proxy.strip(), https_proxy.strip()
        if hp or hsp:
            px: dict[str, str] = {}
            if hp:
                px["http://"] = hp
            if hsp:
                px["https://"] = hsp
            self._proxies = px
            self._trust_env = False
        else:
            self._proxies = None
            self._trust_env = False

    # ── 内部工具 ────────────────────────────────────────────────────

    def _split_system_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str | None, list[dict[str, str]]]:
        """将 system role 消息分离到顶层 ``system`` 字段。"""
        system_parts: list[str] = []
        api_messages: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                api_messages.append({"role": m.role, "content": m.content})
        system = "\n".join(system_parts) if system_parts else None
        return system, api_messages

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[ChatMessage],
        *,
        stream: bool,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        system, api_messages = self._split_system_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": api_messages,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if json_mode:
            # Anthropic 无原生 json_object response_format，通过 system prompt 要求 JSON 输出
            json_instruction = (
                "\n\n你必须仅以 JSON 格式回复，不要包含任何解释或 markdown 标记。"
                "直接输出 JSON 对象。"
            )
            if system:
                payload["system"] = system + json_instruction
            else:
                payload["system"] = json_instruction
        return payload

    # ── httpx 客户端工厂 ────────────────────────────────────────────

    def _httpx_client_kwargs(self, *, stream: bool = False) -> dict[str, Any]:
        timeout = self._stream_timeout if stream else self._timeout
        client_kw: dict[str, Any] = {
            "timeout": timeout,
            "verify": self._verify,
        }
        if self._proxies is not None:
            hp = self._proxies.get("http://")
            hsp = self._proxies.get("https://")
            http_url = hp or hsp
            https_url = hsp or hp
            client_kw["mounts"] = {
                "http://": httpx.HTTPTransport(
                    proxy=http_url,
                    verify=self._verify,
                    trust_env=False,
                ),
                "https://": httpx.HTTPTransport(
                    proxy=https_url,
                    verify=self._verify,
                    trust_env=False,
                ),
            }
            client_kw["trust_env"] = False
        else:
            client_kw["trust_env"] = self._trust_env
        return client_kw

    # ── LLMClient 协议 ──────────────────────────────────────────────

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        if not self._api_key:
            msg = "anthropic_api_key 为空，无法调用 Claude"
            raise RuntimeError(msg)

        url = f"{self._base}/v1/messages"
        headers = self._build_headers()
        payload = self._build_payload(messages, stream=False, json_mode=json_mode)

        try:
            with httpx.Client(**self._httpx_client_kwargs()) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接到 Anthropic API（{url}）：{exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Anthropic API 请求超时（{url}）：{exc}"
            ) from exc

        if response.status_code == 401:
            raise RuntimeError("Anthropic API Key 无效（401），请检查 x-api-key")
        if response.status_code == 429:
            raise RuntimeError("Anthropic API 速率限制（429），请稍后重试")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500] if response.text else ""
            raise RuntimeError(f"Anthropic HTTP {response.status_code}: {detail}") from exc

        data = response.json()
        return self._extract_text(data)

    def stream_completion(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> Iterator[str]:
        if not self._api_key:
            msg = "anthropic_api_key 为空，无法调用 Claude"
            raise RuntimeError(msg)

        url = f"{self._base}/v1/messages"
        headers = self._build_headers()
        payload = self._build_payload(messages, stream=True, json_mode=json_mode)

        try:
            with httpx.Client(**self._httpx_client_kwargs(stream=True)) as client:
                with client.stream(
                    "POST", url, json=payload, headers=headers
                ) as response:
                    if response.status_code == 401:
                        raise RuntimeError(
                            "Anthropic API Key 无效（401），请检查 x-api-key"
                        )
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        detail = (response.read() or b"").decode(
                            "utf-8", errors="replace"
                        )[:500]
                        raise RuntimeError(
                            f"Anthropic HTTP {response.status_code}: {detail}"
                        ) from exc

                    yield from self._parse_sse_stream(response)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接到 Anthropic API（{url}）：{exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Anthropic API 流式请求超时（{url}）：{exc}"
            ) from exc

    # ── SSE 流式解析 ────────────────────────────────────────────────

    @staticmethod
    def _parse_sse_stream(response: httpx.Response) -> Iterator[str]:
        """解析 Anthropic SSE 流，从 content_block_delta 事件中提取文本增量。"""
        pending_event = ""
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                pending_event = line[7:].strip()
                continue
            if line.startswith("data: "):
                raw = line[6:].strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                # 仅从 content_block_delta 提取文本
                if pending_event == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield text
                # message_start / content_block_start / etc. 不产生文本，跳过
                pending_event = ""
                continue

    # ── 非流式响应中提取文本 ────────────────────────────────────────

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """从 Anthropic 非流式响应中拼装所有文本块。"""
        content = data.get("content", [])
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)


# ── 校验工具函数（供 api_config.py 调用）────────────────────────


def validate_anthropic_api_key(
    api_key: str, base_url: str
) -> tuple[bool, str]:
    """向 Anthropic API 发送一个最小请求校验 Key 有效性。

    使用 ``POST /v1/messages``，``max_tokens=1``（最小消耗），
    返回 (是否有效, 错误信息)。
    """
    base = base_url.rstrip("/")
    url = f"{base}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code == 200:
            return True, ""
        if resp.status_code == 401:
            body = resp.json()
            err = body.get("error", {})
            msg = err.get("message", "Unauthorized")
            return False, f"API Key 无效（401）：{msg}"
        if resp.status_code == 400:
            # 可能是模型名不对等，但 Key 有效
            body = resp.json()
            err = body.get("error", {})
            err_type = err.get("type", "")
            # invalid_model / not_found 类错误表示 Key 有效但模型名或请求体有问题
            if err_type in ("invalid_model", "not_found"):
                return True, ""
            msg = err.get("message", "Bad Request")
            return False, f"请求错误（400）：{msg}"
        if resp.status_code == 429:
            return False, "速率限制（429），请稍后重试"
        return (
            False,
            f"验证失败（HTTP {resp.status_code}）：{resp.text[:300]}",
        )
    except httpx.ConnectError:
        return False, f"无法连接到 {base}，请检查 base_url 是否正确"
    except httpx.TimeoutException:
        return False, "连接 Anthropic API 超时"
    except Exception as exc:
        return False, f"验证异常：{exc}"
