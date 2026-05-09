from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@runtime_checkable
class LLMClient(Protocol):
    """模型服务（MS）：OpenAI 兼容对话接口；V0.1 中流式由接入层（I&I）以 SSE 承载。"""

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        """返回助手完整文本（非流式辅助；流式见 harness 中 SSE 实现）。"""
        ...
