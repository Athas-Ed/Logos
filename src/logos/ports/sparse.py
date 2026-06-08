"""Sparse（稀疏关键词）索引端口 — 基于 FTS5 的分块级全文检索。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SparseQueryHit:
    """FTS5 单条命中结果（与 ``VectorQueryHit`` 平行）。"""

    chunk_id: str
    text: str
    norm_text: str
    source_path: str
    entity_id: str
    score: float
    """BM25 / FTS5 原生相关度分（无需外部标准化）。"""


@runtime_checkable
class SparseIndex(Protocol):
    """FTS5 全文索引：chunk 级写入、删除、检索。"""

    def upsert_chunks(
        self,
        *,
        chunk_ids: list[str],
        entity_ids: list[str],
        source_paths: list[str],
        texts: list[str],
        norm_texts: list[str],
    ) -> None:
        ...

    def delete_ids(self, ids: list[str]) -> None:
        ...

    def delete_by_paths(self, source_paths: list[str]) -> None:
        ...

    def search(self, query_text: str, top_k: int) -> list[SparseQueryHit]:
        ...
