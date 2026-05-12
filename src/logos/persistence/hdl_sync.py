"""Scan KSFS and incrementally upsert HSI (hash + mtime)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logos.ports.knowledge_source import SourceDocument
from logos.ports.metadata import MetadataRecord

from ._front_matter import extract_entity_id, extract_title, split_front_matter
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix


@dataclass(frozen=True, slots=True)
class HdlSyncReport:
    """Summary after ``sync_ksfs_hsi``."""

    documents_scanned: int
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


def sync_ksfs_hsi(
    *,
    ksfs_root: Path,
    hsi_db: Path,
) -> HdlSyncReport:
    """
    Scan KSFS for ``*.md``, then incrementally refresh HSI when ``content_hash``
    or ``mtime_ns`` differs. No intermediate mirror directory.
    """
    ksfs_r = ksfs_root.resolve()
    source = FilesystemKnowledgeSource(ksfs_r)
    documents = source.iter_documents()

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
        hsi_upserted=len(upserts),
        hsi_skipped_unchanged=skipped,
        hsi_deleted_stale=deleted,
    )


def default_hsi_db_path(index_root: Path | None = None) -> Path:
    """Default SQLite path (``.index/.high-speed_index``)."""
    base = index_root if index_root is not None else Path(".index")
    return base / ".high-speed_index"
