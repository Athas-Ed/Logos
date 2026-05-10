"""OpenAI 兼容 ``/v1/chat/completions`` 客户端（DeepSeek、OpenAI 等）。"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from logos.ports.llm import ChatMessage

_log = logging.getLogger("logos.infrastructure.llm")


class OpenAICompatibleChatClient:
    """同步调用 ``POST {base_url}/chat/completions``，实现 :class:`~logos.ports.llm.LLMClient` 形态。"""

    __slots__ = (
        "_api_key",
        "_base",
        "_model",
        "_timeout",
        "_transport",
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
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
        verify_ssl: bool = True,
        ca_bundle: str = "",
        http_proxy: str = "",
        https_proxy: str = "",
        no_proxy: str = "",
    ) -> None:
        self._api_key = api_key.strip()
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport

        np = no_proxy.strip()
        if np:
            os.environ["NO_PROXY"] = np
            _log.debug("LLM 客户端设置 NO_PROXY=%s", np)

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
            self._trust_env = True

    def _httpx_client_kwargs(self) -> dict[str, Any]:
        client_kw: dict[str, Any] = {
            "timeout": self._timeout,
            "verify": self._verify,
        }
        if self._transport is not None:
            client_kw["transport"] = self._transport
        elif self._proxies is not None:
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

    def _chat_url_and_headers(self) -> tuple[str, dict[str, str]]:
        url = f"{self._base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        return url, headers

    def stream_completion(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> Iterator[str]:
        if not self._api_key:
            msg = "llm_api_key 为空，无法调用远程模型"
            raise RuntimeError(msg)

        url, headers = self._chat_url_and_headers()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(**self._httpx_client_kwargs()) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code == 401:
                        _log.warning("LLM API 返回 401，请检查 api_key 与 base_url")
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        detail = (response.read() or b"").decode("utf-8", errors="replace")[
                            :500
                        ]
                        msg = f"LLM HTTP {response.status_code}: {detail}"
                        raise RuntimeError(msg) from exc

                    for line in response.iter_lines():
                        if not line:
                            continue
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].lstrip()
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            _log.debug("跳过无法解析的流式行: %s", raw[:200])
                            continue
                        choices = data.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        ch0 = choices[0]
                        if not isinstance(ch0, dict):
                            continue
                        delta = ch0.get("delta")
                        if not isinstance(delta, dict):
                            continue
                        piece = delta.get("content")
                        if piece is None:
                            continue
                        if not isinstance(piece, str):
                            piece = str(piece)
                        if piece:
                            yield piece
        except FileNotFoundError as exc:
            _log.exception(
                "LLM HTTPS 请求出现 FileNotFoundError（常见：ca_bundle / SSL_CERT_FILE / "
                "REQUESTS_CA_BUNDLE 指向了不存在的文件）"
            )
            hint = (
                "请在 config/local.yaml 的 llm.ca_bundle 填写有效证书路径，"
                "或检查环境变量 SSL_CERT_FILE、REQUESTS_CA_BUNDLE；"
                "亦可暂时将 llm.verify_ssl 设为 false（不推荐）。"
            )
            raise RuntimeError(f"{hint} 原始错误: {exc!s}") from exc

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        if not self._api_key:
            msg = "llm_api_key 为空，无法调用远程模型"
            raise RuntimeError(msg)

        url, headers = self._chat_url_and_headers()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            **headers,
            "Accept": "application/json",
        }

        try:
            with httpx.Client(**self._httpx_client_kwargs()) as client:
                response = client.post(url, json=payload, headers=headers)
        except FileNotFoundError as exc:
            fn = getattr(exc, "filename", None)
            _log.exception(
                "LLM HTTPS 请求出现 FileNotFoundError（常见：ca_bundle / SSL_CERT_FILE / "
                "REQUESTS_CA_BUNDLE 指向了不存在的文件）"
            )
            hint = (
                "请在 config/local.yaml 的 llm.ca_bundle 填写有效证书路径，"
                "或检查环境变量 SSL_CERT_FILE、REQUESTS_CA_BUNDLE；"
                "亦可暂时将 llm.verify_ssl 设为 false（不推荐）。"
            )
            raise RuntimeError(f"{hint} 原始错误: {exc!s}") from exc

        if response.status_code == 401:
            _log.warning("LLM API 返回 401，请检查 api_key 与 base_url")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500] if response.text else ""
            msg = f"LLM HTTP {response.status_code}: {detail}"
            raise RuntimeError(msg) from exc

        data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            msg = f"LLM 响应缺少 choices：{data!r:.500}"
            raise RuntimeError(msg)

        first = choices[0]
        if not isinstance(first, dict):
            msg = "LLM choices[0] 格式无效"
            raise RuntimeError(msg)

        message = first.get("message")
        if not isinstance(message, dict):
            msg = "LLM 响应缺少 message 对象"
            raise RuntimeError(msg)

        content = message.get("content")
        if content is None:
            return ""
        if not isinstance(content, str):
            return str(content)
        return content
