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
    """Vector index (e.g. Chroma) — add / delete / similarity search."""

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
