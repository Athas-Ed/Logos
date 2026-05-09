from __future__ import annotations

from typing import Any

from logos.ports.vector import VectorQueryHit


def _require_chromadb() -> Any:
    try:
        import chromadb
    except ImportError as e:  # pragma: no cover - minimal CI env
        msg = (
            "ChromaSemanticStore requires `chromadb`. "
            "Install with `pip install chromadb`."
        )
        raise ImportError(msg) from e
    return chromadb


class ChromaSemanticStore:
    """Chroma persistent client implementing `SemanticStore`."""

    def __init__(self, *, persist_directory: str, collection_name: str) -> None:
        chromadb = _require_chromadb()
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]] | None = None,
    ) -> None:
        if not ids:
            return
        if not (len(ids) == len(texts) == len(embeddings)):
            raise ValueError("ids, texts, and embeddings must have the same length")
        md = metadatas if metadatas is not None else None
        if md is not None and len(md) != len(ids):
            raise ValueError("metadatas must match ids length")
        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=md,
        )

    def delete_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        self._collection.delete(ids=ids)

    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        if top_k <= 0:
            return []
        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )
        id_batch = raw.get("ids") or []
        doc_batch = raw.get("documents") or []
        dist_batch = raw.get("distances") or []
        meta_batch = raw.get("metadatas") or []
        if not id_batch:
            return []
        ids = id_batch[0]
        docs = (doc_batch[0] if doc_batch else []) or []
        dists = (dist_batch[0] if dist_batch else []) or []
        metas = (meta_batch[0] if meta_batch else []) or []

        hits: list[VectorQueryHit] = []
        for i, chunk_id in enumerate(ids):
            text = docs[i] if i < len(docs) else ""
            dist = float(dists[i]) if i < len(dists) else 0.0
            score = _distance_to_score(dist)
            meta = metas[i] if i < len(metas) else {}
            path = ""
            if isinstance(meta, dict):
                p = meta.get("source_path")
                if isinstance(p, str):
                    path = p
            hits.append(
                VectorQueryHit(
                    chunk_id=str(chunk_id),
                    text=text or "",
                    score=score,
                    source_path=path,
                )
            )
        return hits


def _distance_to_score(distance: float) -> float:
    """Chroma cosine space uses distance = 1 - cos_sim in [0, 2] typically."""
    if distance <= 1.0:
        return max(0.0, 1.0 - distance)
    return 1.0 / (1.0 + distance)
