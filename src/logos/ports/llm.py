from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@runtime_checkable
class LLMClient(Protocol):
    """模型服务（MS）：OpenAI 兼容对话接口；I&I 将 ``stream_completion`` 增量映射为 SSE ``delta``。"""

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        """返回助手完整文本。"""
        ...

    def stream_completion(
        self, messages: list[ChatMessage], *, json_mode: bool = False
    ) -> Iterator[str]:
        """按上游模型流式输出增量文本片段（可能为空字符串，调用方宜忽略空段）。"""
        ...
