"""可变 LLM 引用包装器，支持运行时热替换 LLM 实现。

在 ``app.py:main()`` 中将 LLM 实例包装为 :class:`LLMRef`，
通过 ``swap()`` 可在不重建 FastAPI 应用的前提下替换 LLM 后端。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from logos.ports.llm import LLMClient


class LLMRef:
    """实现 :class:`LLMClient` 协议的可变包装器。

    ``swap()`` 在运行时替换内部 LLM 实例，所有通过 ``LLMDep``
    获取引用的请求/SSE 流自动使用新实例。
    """

    __slots__ = ("_llm",)

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    # ── LLMClient 协议 ──────────────────────────────────────────────

    def complete(self, messages: list[Any], *, json_mode: bool = False) -> str:
        return self._llm.complete(messages, json_mode=json_mode)

    def stream_completion(
        self, messages: list[Any], *, json_mode: bool = False
    ) -> Iterator[str]:
        return self._llm.stream_completion(messages, json_mode=json_mode)

    # ── 运行时控制 ──────────────────────────────────────────────────

    def swap(self, new_llm: LLMClient) -> None:
        """热替换内部 LLM 实现（线程安全：Python GIL 保护赋值）。"""
        self._llm = new_llm

    @property
    def is_stub(self) -> bool:
        """当前是否为桩实现（无有效 API Key）。"""
        return getattr(self._llm, "_IS_STUB", False)
