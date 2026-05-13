from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Citation:
    """与 ``API-V0.2.md`` 中 SSE ``citations.items`` 字段对齐（path / snippet / score）。"""

    path: str
    snippet: str
    score: float


@runtime_checkable
class RetrievalService(Protocol):
    """融合检索：HSI（高速索引）+ SVS（语义向量库）。"""

    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        ...
