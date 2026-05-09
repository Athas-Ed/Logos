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
    """MS: OpenAI-compatible chat (streaming handled at I&I layer in V0.1)."""

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        """Return assistant text (non-streaming helper; SSE built in harness later)."""
        ...
