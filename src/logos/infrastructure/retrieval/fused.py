from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from logos.ports.embedding import TextEmbedder
from logos.ports.metadata import MetadataIndex, MetadataRecord
from logos.ports.retrieval import Citation
from logos.ports.sparse import SparseIndex
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


_log = logging.getLogger("logos.retrieval.fused")


@dataclass
class FusedRetrievalService:
    """Fuses HSI + SVS + Sparse（可选）多路召回。

    - HSI（``MetadataIndex``）：路径/title 子串弱匹配
    - SVS（``SemanticStore``）：分块向量相似度
    - Sparse（``SparseIndex``，可选）：FTS5 全文关键词
    """

    metadata_index: MetadataIndex
    semantic_store: SemanticStore
    embedder: TextEmbedder
    #: 可选稀疏全文索引（FTS5）。
    sparse_index: SparseIndex | None = None
    #: 若二者均非空，则在 ``query`` 前对 KSFS 做 HSI/SVS 增量对账。
    lazy_hsi_ksfs_root: Path | None = None
    lazy_hsi_db_path: Path | None = None
    #: 若非空且已装配真实向量库，每次 ``query`` 前执行 ``sync_ksfs_svs_incremental``。
    lazy_svs_state_db: Path | None = None
    #: 若非空，每次 ``query`` 前执行 ``sync_ksfs_sparse_incremental``（内含 HSI 对账）。
    lazy_sparse_db_path: Path | None = None
    #: 为 True 时每次 ``query`` 前扫描 KSFS 并刷新索引；为 False 时仅进程内首次登记。
    refresh_indexes_on_query: bool = True

    def _refresh_indexes_from_ksfs(self) -> None:
        root = self.lazy_hsi_ksfs_root
        dbp = self.lazy_hsi_db_path
        if root is None or dbp is None:
            return
        if not self.refresh_indexes_on_query:
            from logos.persistence.registration import ensure_ksfs_hsi_registered

            report = ensure_ksfs_hsi_registered(ksfs_root=root, hsi_db=dbp)
            if report is not None:
                _log.info(
                    "HSI 懒登记完成：扫描 %s 条，写入 %s 条，跳过 %s 条",
                    report.documents_scanned,
                    report.hsi_upserted,
                    report.hsi_skipped_unchanged,
                )
            return

        # 决定哪些索引需要同步
        needs_svs = self.lazy_svs_state_db is not None
        needs_sparse = self.lazy_sparse_db_path is not None and self.sparse_index is not None

        if needs_svs:
            from logos.persistence.chroma_bootstrap import sync_ksfs_svs_incremental

            srep = sync_ksfs_svs_incremental(
                ksfs_root=root,
                hsi_db=dbp,
                store=self.semantic_store,
                embedder=self.embedder,
                svs_state_db=self.lazy_svs_state_db,
            )
            if (
                srep.documents_vectorized > 0
                or srep.chunks_upserted > 0
                or srep.chunks_deleted_stale > 0
            ):
                _log.info(
                    "检索前 SVS 增量：扫描 %s 文档；向量化 %s 文件；upsert 块 %s；删块 %s",
                    srep.hsi_documents_scanned,
                    srep.documents_vectorized,
                    srep.chunks_upserted,
                    srep.chunks_deleted_stale,
                )
            else:
                _log.debug(
                    "检索前 SVS 对账：HSI 扫描 %s，无变更（跳过向量化 %s）",
                    srep.hsi_documents_scanned,
                    srep.documents_skipped_unchanged,
                )

        if needs_sparse:
            from logos.persistence.sparse_fts import sync_ksfs_sparse_incremental

            srep = sync_ksfs_sparse_incremental(
                ksfs_root=root,
                hsi_db=dbp,
                sparse_index=self.sparse_index,
                sparse_db=self.lazy_sparse_db_path,
            )
            if (
                srep.chunks_upserted > 0
                or srep.chunks_deleted_stale > 0
            ):
                _log.info(
                    "检索前 Sparse 增量：扫描 %s 文档；索引 %s 文件；upsert 块 %s；删块 %s",
                    srep.hsi_documents_scanned,
                    srep.documents_indexed,
                    srep.chunks_upserted,
                    srep.chunks_deleted_stale,
                )
            else:
                _log.debug(
                    "检索前 Sparse 对账：HSI 扫描 %s，无变更（跳过索引 %s）",
                    srep.hsi_documents_scanned,
                    srep.documents_skipped_unchanged,
                )

        if not needs_svs and not needs_sparse:
            from logos.persistence.hdl_sync import sync_ksfs_hsi

            report = sync_ksfs_hsi(ksfs_root=root, hsi_db=dbp)
            if report.hsi_upserted > 0 or report.hsi_deleted_stale > 0:
                _log.info(
                    "检索前 HSI 增量：扫描 %s 条，写入 %s 条，删除陈旧 %s 条",
                    report.documents_scanned,
                    report.hsi_upserted,
                    report.hsi_deleted_stale,
                )
            else:
                _log.debug(
                    "检索前 HSI 对账：扫描 %s 条，无正文/mtime 变更",
                    report.documents_scanned,
                )

    def query(self, *, text: str, top_k: int = 8) -> list[Citation]:
        if top_k <= 0:
            return []
        self._refresh_indexes_from_ksfs()
        q = text.strip()
        by_path: dict[str, tuple[float, str]] = {}

        # SVS — 向量相似度
        if q:
            qvec = self.embedder.embed([q])[0]
            for hit in self.semantic_store.query(qvec, top_k=top_k):
                path = hit.source_path.strip() or hit.chunk_id
                snip = _snippet(hit.text)
                prev = by_path.get(path)
                score = float(hit.score)
                if prev is None or score > prev[0]:
                    by_path[path] = (score, snip)

        # HSI — 路径/title 子串弱匹配
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

        # Sparse — FTS5 全文关键词（可选）
        if self.sparse_index is not None and q:
            for hit in self.sparse_index.search(q, top_k=top_k):
                path = hit.source_path.strip()
                snip = _snippet(hit.text)
                prev = by_path.get(path)
                score = float(hit.score)
                if prev is None or score > prev[0]:
                    by_path[path] = (score, snip)

        ranked = sorted(by_path.items(), key=lambda kv: kv[1][0], reverse=True)[
            :top_k
        ]
        return [
            Citation(path=path, snippet=snippet, score=score)
            for path, (score, snippet) in ranked
        ]
