from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Citation:
    """Aligned with SSE `citations.items` in API-V0.1.md (path / snippet / score)."""

    path: str
    snippet: str
    score: float


@runtime_checkable
class RetrievalService(Protocol):
    """Fused HSI + SVS retrieval."""

    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        ...
