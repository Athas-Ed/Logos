from __future__ import annotations

from dataclasses import dataclass

from logos.ports.embedding import TextEmbedder
from logos.ports.metadata import MetadataIndex, MetadataRecord
from logos.ports.retrieval import Citation
from logos.ports.vector import SemanticStore


def _hsi_path_prefix(query: str) -> str | None:
    """If *query* looks path-like, use its first token as `search_paths` prefix."""
    q = query.strip()
    if not q or ("/" not in q and "\\" not in q):
        return None
    return q.split()[0]


def _snippet(text: str, max_len: int = 240) -> str:
    t = text.strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _hsi_keyword_score(query: str, rec: MetadataRecord) -> float:
    q = query.strip().lower()
    if not q:
        return 0.0
    path_l = rec.source_path.lower()
    title_l = rec.title.lower()
    if q in path_l:
        return 0.82
    if q in title_l:
        return 0.74
    parts = [p for p in q.split() if len(p) > 1]
    if parts and any(p in path_l or p in title_l for p in parts):
        return 0.62
    # 中文等：去掉空白后整段是否命中标题/路径（如「山巅城堡 设定」→「山巅城堡」）
    compact = "".join(q.split())
    if len(compact) >= 2 and (compact in path_l or compact in title_l):
        return 0.58
    return 0.0


@dataclass
class FusedRetrievalService:
    """Fuses HSI (`MetadataIndex`) path/title matches with SVS (`SemanticStore`) similarity."""

    metadata_index: MetadataIndex
    semantic_store: SemanticStore
    embedder: TextEmbedder

    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        if top_k <= 0:
            return []
        q = text.strip()
        by_path: dict[str, tuple[float, str]] = {}

        # SVS
        if q:
            qvec = self.embedder.embed([q])[0]
            for hit in self.semantic_store.query(qvec, top_k=top_k):
                path = hit.source_path.strip() or hit.chunk_id
                snip = _snippet(hit.text)
                prev = by_path.get(path)
                score = float(hit.score)
                if prev is None or score > prev[0]:
                    by_path[path] = (score, snip)

        # HSI — bounded scan + keyword rank (`MetadataIndex` has no full-text API).
        path_prefix = _hsi_path_prefix(q)
        hsi_limit = (
            max(top_k * 8, 32)
            if path_prefix is not None
            else max(top_k * 50, 256)
        )
        hsi_rows = self.metadata_index.search_paths(prefix=path_prefix, limit=hsi_limit)
        for rec in hsi_rows:
            hs = _hsi_keyword_score(q, rec)
            if hs <= 0.0:
                continue
            path = rec.source_path
            snip = _snippet(rec.title or path)
            prev = by_path.get(path)
            if prev is None or hs > prev[0]:
                by_path[path] = (hs, snip)

        ranked = sorted(by_path.items(), key=lambda kv: kv[1][0], reverse=True)[
            :top_k
        ]
        return [
            Citation(path=path, snippet=snippet, score=score)
            for path, (score, snippet) in ranked
        ]
