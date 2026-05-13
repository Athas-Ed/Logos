"""KSFS → SVS（Chroma）：§5 分块、§5.5 ``chunk_id``、chunk 级增量同步。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logos.ports.embedding import TextEmbedder
from logos.ports.vector import SemanticStore

from ._front_matter import split_front_matter
from .hdl_sync import sync_ksfs_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .svs_chunking import build_chunk_records, compute_chunk_id
from .svs_sync_state import SvsEmbeddingStateStore


@dataclass(frozen=True, slots=True)
class SvsSyncReport:
    """``sync_ksfs_svs_incremental`` 摘要。"""

    hsi_documents_scanned: int
    documents_vectorized: int
    documents_skipped_unchanged: int
    chunks_upserted: int
    chunks_deleted_stale: int


def default_svs_state_db_path(index_root: Path | None = None) -> Path:
    """默认 SVS 增量状态库路径（与 HSI / Chroma 同置于 ``.index`` 下）。"""
    base = index_root if index_root is not None else Path(".index")
    return base / ".svs_chunk_index.sqlite"


def _truncate_for_embed(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def sync_ksfs_svs_incremental(
    *,
    ksfs_root: Path,
    hsi_db: Path,
    store: SemanticStore,
    embedder: TextEmbedder,
    svs_state_db: Path,
    max_embed_chars_per_chunk: int = 12_000,
) -> SvsSyncReport:
    """
    先 ``sync_ksfs_hsi``（HSI 自身会跳过未变行），再按 HSI 的 ``content_hash`` / ``mtime_ns``
    做 **chunk 级** Chroma 增量：未变整文件跳过嵌入；已变则删旧 ``chunk_id`` 再 upsert。
    """
    ksfs_r = ksfs_root.resolve()
    hsi_path = hsi_db.resolve()
    state_path = svs_state_db.resolve()

    hsi_report = sync_ksfs_hsi(ksfs_root=ksfs_r, hsi_db=hsi_path)
    hsi = SqliteMetadataIndex(hsi_path)
    state_store = SvsEmbeddingStateStore(state_path)
    prev = state_store.load_all()

    src = FilesystemKnowledgeSource(ksfs_r)
    documents = src.iter_documents()
    keep = frozenset(document_rel_posix(d, ksfs_r) for d in documents)

    stale_paths = [p for p in prev if p not in keep]
    deleted_vec = 0
    for p in stale_paths:
        old_ids = list(prev[p].chunk_ids)
        if old_ids:
            store.delete_ids(old_ids)
            deleted_vec += len(old_ids)
    if stale_paths:
        state_store.delete_paths(stale_paths)

    active = {p: prev[p] for p in prev if p in keep}
    doc_skipped = 0
    doc_vec = 0
    chunks_up = 0

    for doc in documents:
        rel = document_rel_posix(doc, ksfs_r)
        row = hsi.fetch_by_paths([rel]).get(rel)
        if row is None:
            continue

        _, body = split_front_matter(doc.text)
        records = build_chunk_records(rel, body or "")
        chunk_ids: list[str] = []
        texts: list[str] = []
        for rec in records:
            t = _truncate_for_embed(rec.text, max_embed_chars_per_chunk)
            cid = compute_chunk_id(
                entity_id=row.entity_id,
                chunk_index=rec.chunk_index,
                chunk_text=t,
            )
            chunk_ids.append(cid)
            texts.append(t)

        prior = active.get(rel)
        unchanged = (
            prior is not None
            and prior.entity_id == row.entity_id
            and prior.content_hash == row.content_hash
            and prior.mtime_ns == row.mtime_ns
            and prior.chunk_ids == tuple(chunk_ids)
        )
        if unchanged:
            doc_skipped += 1
            continue

        if prior is not None and prior.chunk_ids:
            store.delete_ids(list(prior.chunk_ids))
            deleted_vec += len(prior.chunk_ids)

        if not chunk_ids:
            state_store.delete_paths([rel])
            doc_vec += 1
            continue

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
        store.upsert_chunks(
            ids=chunk_ids,
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        state_store.upsert_row(
            source_path=rel,
            entity_id=row.entity_id,
            content_hash=row.content_hash,
            mtime_ns=row.mtime_ns,
            chunk_ids=tuple(chunk_ids),
        )
        doc_vec += 1
        chunks_up += len(chunk_ids)

    return SvsSyncReport(
        hsi_documents_scanned=hsi_report.documents_scanned,
        documents_vectorized=doc_vec,
        documents_skipped_unchanged=doc_skipped,
        chunks_upserted=chunks_up,
        chunks_deleted_stale=deleted_vec,
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
    兼容旧名：等价于 ``sync_ksfs_svs_incremental``，返回 **本趟 upsert 的块数**。

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
    rep = sync_ksfs_svs_incremental(
        ksfs_root=root,
        hsi_db=hsi,
        store=store,
        embedder=embedder,
        svs_state_db=state,
        max_embed_chars_per_chunk=max_embed_chars_per_chunk,
    )
    return rep.chunks_upserted
