"""Orchestrate KSS → LKC → HSI with hash + mtime incremental upserts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logos.ports.knowledge_source import SourceDocument
from logos.ports.metadata import MetadataRecord

from ._front_matter import extract_entity_id, extract_title, split_front_matter
from .hsi_sqlite import SqliteMetadataIndex
from .kss_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .lkc_sync import LkcSyncResult, sync_lkc_from_documents


@dataclass(frozen=True, slots=True)
class HdlSyncReport:
    """Summary after ``sync_ksfs_lkc_hsi``."""

    documents_scanned: int
    lkc: LkcSyncResult
    hsi_upserted: int
    hsi_skipped_unchanged: int
    hsi_deleted_stale: int


def _metadata_for_doc(doc: SourceDocument, *, ksfs_root: Path) -> MetadataRecord:
    rel = document_rel_posix(doc, ksfs_root)
    headers, body = split_front_matter(doc.text)
    title = extract_title(headers, body=body, fallback_name=doc.path.name)
    entity_id = extract_entity_id(headers, rel_posix=rel)
    return MetadataRecord(
        entity_id=entity_id,
        title=title,
        source_path=rel,
        content_hash=doc.content_hash,
        mtime_ns=doc.mtime_ns,
    )


def sync_ksfs_lkc_hsi(
    *,
    ksfs_root: Path,
    lkc_root: Path,
    hsi_db: Path,
    prune: bool = True,
) -> HdlSyncReport:
    """
    Scan KSFS (KSS), mirror normalized Markdown into LKC, then incrementally
    refresh HSI rows when ``content_hash`` or ``mtime_ns`` differs.
    """
    ksfs_r = ksfs_root.resolve()
    kss = FilesystemKnowledgeSource(ksfs_r)
    documents = kss.iter_documents()
    lkc = sync_lkc_from_documents(
        ksfs_root=ksfs_r,
        lkc_root=lkc_root.resolve(),
        documents=documents,
        prune=prune,
    )

    hsi = SqliteMetadataIndex(hsi_db)
    rel_paths = [document_rel_posix(d, ksfs_r) for d in documents]
    existing = hsi.fetch_by_paths(rel_paths)

    upserts: list[MetadataRecord] = []
    skipped = 0
    for doc in documents:
        rec = _metadata_for_doc(doc, ksfs_root=ksfs_r)
        old = existing.get(rec.source_path)
        if (
            old is not None
            and old.content_hash == rec.content_hash
            and old.mtime_ns == rec.mtime_ns
        ):
            skipped += 1
            continue
        upserts.append(rec)

    hsi.upsert(upserts)
    keep = frozenset(rel_paths)
    deleted = hsi.delete_not_in(keep)

    return HdlSyncReport(
        documents_scanned=len(documents),
        lkc=lkc,
        hsi_upserted=len(upserts),
        hsi_skipped_unchanged=skipped,
        hsi_deleted_stale=deleted,
    )


def default_hsi_db_path(index_root: Path | None = None) -> Path:
    """Default SQLite path per SPEC (``.index/.high-speed_index``)."""
    base = index_root if index_root is not None else Path(".index")
    return base / ".high-speed_index"
