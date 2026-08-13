"""KSFS → 索引（SVS / Sparse）chunk 级增量同步。

Candidate 2（架构深化）：``sync_ksfs_indexes`` 为唯一 chunk 级增量入口——
**一次** ``sync_ksfs_hsi`` + **一次** KSFS 遍历，同 loop 按装配分支双写
SVS（Chroma 向量）与 Sparse（FTS5 关键词），消除旧两条并行管线的重复扫描。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logos.ports.embedding import TextEmbedder
from logos.ports.sparse import SparseIndex
from logos.ports.vector import SemanticStore

from ._front_matter import split_front_matter
from .hdl_sync import sync_ksfs_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .svs_chunking import build_chunk_records, compute_chunk_id
from .svs_sync_state import DocSyncStateStore

_SVS_STATE_TABLE = "svs_doc_embedding_state"
_SPARSE_STATE_TABLE = "sparse_sync_state"


@dataclass(frozen=True, slots=True)
class IndexesSyncReport:
    """``sync_ksfs_indexes`` 摘要（未装配的分支计数为 0）。"""

    hsi_documents_scanned: int
    svs_documents_vectorized: int
    svs_documents_skipped_unchanged: int
    svs_chunks_upserted: int
    sparse_documents_indexed: int
    sparse_documents_skipped_unchanged: int
    sparse_chunks_upserted: int
    chunks_deleted_stale: int


def default_svs_state_db_path(index_root: Path | None = None) -> Path:
    """默认 SVS 增量状态库路径（与 HSI / Chroma 同置于 ``.index`` 下）。"""
    base = index_root if index_root is not None else Path(".index")
    return base / ".svs_chunk_index.sqlite"


def _truncate_for_embed(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def sync_ksfs_indexes(
    *,
    ksfs_root: Path,
    hsi_db: Path,
    semantic_store: SemanticStore | None = None,
    embedder: TextEmbedder | None = None,
    svs_state_db: Path | None = None,
    sparse_index: SparseIndex | None = None,
    sparse_db: Path | None = None,
    max_embed_chars_per_chunk: int = 12_000,
) -> IndexesSyncReport:
    """
    一次 HSI 对账 + 一次 KSFS 遍历，按装配分支同步 SVS / Sparse。

    - SVS 分支启用：``semantic_store``/``embedder``/``svs_state_db`` 均非空；
    - Sparse 分支启用：``sparse_index``/``sparse_db`` 均非空；
    - 各分支按 HSI 的 ``content_hash`` / ``mtime_ns`` 做 chunk 级增量：
      未变整文件跳过；已变则删旧 ``chunk_id`` 再 upsert。
    """
    ksfs_r = ksfs_root.resolve()
    hsi_path = hsi_db.resolve()
    uses_svs = (
        semantic_store is not None
        and embedder is not None
        and svs_state_db is not None
    )
    uses_sparse = sparse_index is not None and sparse_db is not None

    hsi_report = sync_ksfs_hsi(ksfs_root=ksfs_r, hsi_db=hsi_path)
    hsi = SqliteMetadataIndex(hsi_path)

    if uses_svs:
        svs_state = DocSyncStateStore(
            svs_state_db.resolve(), table=_SVS_STATE_TABLE
        )
        prev_svs = svs_state.load_all()
    if uses_sparse:
        sparse_state = DocSyncStateStore(
            sparse_db.resolve(), table=_SPARSE_STATE_TABLE
        )
        prev_sparse = sparse_state.load_all()

    src = FilesystemKnowledgeSource(ksfs_r)
    documents = src.iter_documents()
    keep = frozenset(document_rel_posix(d, ksfs_r) for d in documents)

    deleted = 0
    if uses_svs:
        stale = [p for p in prev_svs if p not in keep]
        stale_ids: list[str] = []
        for p in stale:
            stale_ids.extend(prev_svs[p].chunk_ids)
        if stale_ids:
            semantic_store.delete_ids(stale_ids)
            deleted += len(stale_ids)
        if stale:
            svs_state.delete_paths(stale)
    if uses_sparse:
        stale = [p for p in prev_sparse if p not in keep]
        stale_ids = []
        for p in stale:
            stale_ids.extend(prev_sparse[p].chunk_ids)
        if stale_ids:
            sparse_index.delete_ids(stale_ids)
            deleted += len(stale_ids)
        if stale:
            sparse_state.delete_paths(stale)

    active_svs = {p: prev_svs[p] for p in prev_svs if p in keep} if uses_svs else {}
    active_sparse = (
        {p: prev_sparse[p] for p in prev_sparse if p in keep} if uses_sparse else {}
    )

    doc_vec = 0
    doc_skipped = 0
    chunks_up = 0
    doc_idx = 0
    sparse_skipped = 0
    sparse_chunks_up = 0

    for doc in documents:
        rel = document_rel_posix(doc, ksfs_r)
        row = hsi.fetch_by_paths([rel]).get(rel)
        if row is None:
            continue

        _, body = split_front_matter(doc.text)
        records = build_chunk_records(rel, body or "")

        if uses_svs:
            svs_ids: list[str] = []
            texts: list[str] = []
            for rec in records:
                t = _truncate_for_embed(rec.text, max_embed_chars_per_chunk)
                svs_ids.append(
                    compute_chunk_id(
                        entity_id=row.entity_id,
                        chunk_index=rec.chunk_index,
                        chunk_text=t,
                    )
                )
                texts.append(t)
            prior = active_svs.get(rel)
            unchanged = (
                prior is not None
                and prior.entity_id == row.entity_id
                and prior.content_hash == row.content_hash
                and prior.mtime_ns == row.mtime_ns
                and prior.chunk_ids == tuple(svs_ids)
            )
            if unchanged:
                doc_skipped += 1
            else:
                if prior is not None and prior.chunk_ids:
                    semantic_store.delete_ids(list(prior.chunk_ids))
                    deleted += len(prior.chunk_ids)
                if not svs_ids:
                    svs_state.delete_paths([rel])
                    doc_vec += 1
                else:
                    embeddings = embedder.embed(texts)
                    metadatas: list[dict[str, str]] = []
                    for rec in records:
                        h = rec.heading if rec.heading else " "
                        metadatas.append(
                            {
                                "source_path": rel,
                                "entity_id": str(row.entity_id),
                                "chunk_index": str(rec.chunk_index),
                                "heading": h[:512],
                            }
                        )
                    semantic_store.upsert_chunks(
                        ids=svs_ids,
                        texts=texts,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )
                    svs_state.upsert_row(
                        source_path=rel,
                        entity_id=row.entity_id,
                        content_hash=row.content_hash,
                        mtime_ns=row.mtime_ns,
                        chunk_ids=tuple(svs_ids),
                    )
                    doc_vec += 1
                    chunks_up += len(svs_ids)

        if uses_sparse:
            sp_ids: list[str] = []
            texts = []
            norm_texts: list[str] = []
            for rec in records:
                sp_ids.append(
                    compute_chunk_id(
                        entity_id=row.entity_id,
                        chunk_index=rec.chunk_index,
                        chunk_text=rec.text,
                    )
                )
                texts.append(rec.text)
                norm_texts.append(rec.norm_text)
            prior = active_sparse.get(rel)
            unchanged = (
                prior is not None
                and prior.entity_id == row.entity_id
                and prior.content_hash == row.content_hash
                and prior.mtime_ns == row.mtime_ns
                and prior.chunk_ids == tuple(sp_ids)
            )
            if unchanged:
                sparse_skipped += 1
            else:
                if prior is not None and prior.chunk_ids:
                    sparse_index.delete_ids(list(prior.chunk_ids))
                    deleted += len(prior.chunk_ids)
                if not sp_ids:
                    sparse_state.delete_paths([rel])
                    doc_idx += 1
                else:
                    sparse_index.upsert_chunks(
                        chunk_ids=sp_ids,
                        entity_ids=[row.entity_id] * len(sp_ids),
                        source_paths=[rel] * len(sp_ids),
                        texts=texts,
                        norm_texts=norm_texts,
                    )
                    sparse_state.upsert_row(
                        source_path=rel,
                        entity_id=row.entity_id,
                        content_hash=row.content_hash,
                        mtime_ns=row.mtime_ns,
                        chunk_ids=tuple(sp_ids),
                    )
                    doc_idx += 1
                    sparse_chunks_up += len(sp_ids)

    return IndexesSyncReport(
        hsi_documents_scanned=hsi_report.documents_scanned,
        svs_documents_vectorized=doc_vec,
        svs_documents_skipped_unchanged=doc_skipped,
        svs_chunks_upserted=chunks_up,
        sparse_documents_indexed=doc_idx,
        sparse_documents_skipped_unchanged=sparse_skipped,
        sparse_chunks_upserted=sparse_chunks_up,
        chunks_deleted_stale=deleted,
    )


def reindex_ksfs_to_semantic_store(
    *,
    ksfs_root: Path,
    store: SemanticStore,
    embedder: TextEmbedder,
    index_root: Path | None = None,
    hsi_db: Path | None = None,
    svs_state_db: Path | None = None,
    max_embed_chars_per_chunk: int = 12_000,
) -> int:
    """
    兼容旧名：等价于 ``sync_ksfs_indexes``（仅 SVS 分支），返回 **本趟 upsert 的块数**。

    路径解析：优先 ``hsi_db`` / ``svs_state_db``；否则若提供 ``index_root``（仓库
    ``paths.index_root``），则 HSI 为 ``index_root/.high-speed_index``，SVS 状态为
    ``default_svs_state_db_path(index_root)``；再否则退化为 ``ksfs_root.parent/.index``
    （仅适用于测试布局）。
    """
    root = ksfs_root.resolve()
    if hsi_db is not None:
        hsi = hsi_db.resolve()
    elif index_root is not None:
        hsi = Path(index_root).resolve() / ".high-speed_index"
    else:
        hsi = root.parent / ".index" / ".high-speed_index"

    if svs_state_db is not None:
        state = svs_state_db.resolve()
    elif index_root is not None:
        state = default_svs_state_db_path(Path(index_root).resolve())
    else:
        state = default_svs_state_db_path(root.parent / ".index")
    rep = sync_ksfs_indexes(
        ksfs_root=root,
        hsi_db=hsi,
        semantic_store=store,
        embedder=embedder,
        svs_state_db=state,
        max_embed_chars_per_chunk=max_embed_chars_per_chunk,
    )
    return rep.svs_chunks_upserted
