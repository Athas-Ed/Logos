from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VectorQueryHit:
    chunk_id: str
    text: str
    score: float
    source_path: str


@runtime_checkable
class SemanticStore(Protocol):
    """向量索引（例如 Chroma）：写入分块、删除、相似度检索。"""

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]] | None = None,
    ) -> None:
        ...

    def delete_ids(self, ids: list[str]) -> None:
        ...

    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        ...
