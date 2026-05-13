"""Scan KSFS and incrementally upsert HSI (hash + mtime)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logos.ports.knowledge_source import SourceDocument
from logos.ports.metadata import MetadataRecord

from ._front_matter import (
    ensure_front_matter_id,
    extract_numeric_entity_id,
    extract_title,
    split_front_matter,
)
from ._hash import content_hash_hex
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix

_ID_SEED = 10_000


@dataclass(frozen=True, slots=True)
class HdlSyncReport:
    """Summary after ``sync_ksfs_hsi``."""

    documents_scanned: int
    hsi_upserted: int
    hsi_skipped_unchanged: int
    hsi_deleted_stale: int
    hsi_ids_allocated: int
    fm_id_writebacks: int
    hsi_id_conflicts_resolved: int


def _body_content_hash(text: str) -> str:
    headers, body = split_front_matter(text)
    _ = headers
    payload = body if body.strip() else text
    return content_hash_hex(payload)


def _metadata_for_doc(
    doc: SourceDocument,
    *,
    ksfs_root: Path,
    entity_id: str,
) -> MetadataRecord:
    rel = document_rel_posix(doc, ksfs_root)
    headers, body = split_front_matter(doc.text)
    title = extract_title(headers, body=body, fallback_name=doc.path.name)
    return MetadataRecord(
        entity_id=entity_id,
        title=title,
        source_path=rel,
        content_hash=_body_content_hash(doc.text),
        mtime_ns=doc.mtime_ns,
    )


def _next_numeric_id(
    *,
    counter: int,
    occupancy: dict[str, str],
) -> tuple[str, int]:
    """Return a fresh numeric id not present in *occupancy* keys."""
    n = counter
    while True:
        n += 1
        cand = str(n)
        if cand not in occupancy:
            return cand, n


def _max_numeric_from_declarations(
    decls: list[str | None],
    *,
    hsi_max: int,
) -> int:
    best = max(_ID_SEED, hsi_max)
    for raw in decls:
        if raw is not None and raw.isdigit():
            best = max(best, int(raw))
    return best


def sync_ksfs_hsi(
    *,
    ksfs_root: Path,
    hsi_db: Path,
) -> HdlSyncReport:
    """
    Scan KSFS for ``*.md``, assign stable numeric ``id`` (KSFS §3.2), write ``id:`` into
    front matter on conflict or first-time allocation (§3.4), then incrementally refresh
    HSI when **body** content hash or ``mtime_ns`` differs (§3.2 途径 A).
    """
    ksfs_r = ksfs_root.resolve()
    source = FilesystemKnowledgeSource(ksfs_r)
    documents = source.iter_documents()
    rel_paths = [document_rel_posix(d, ksfs_r) for d in documents]
    keep = frozenset(rel_paths)

    hsi = SqliteMetadataIndex(hsi_db)
    hsi_max = hsi.max_numeric_entity_id()
    occupancy = hsi.entity_id_to_path_for_keep(keep)

    id_allocated = 0
    fm_writebacks = 0
    conflicts = 0

    # --- Phase 1: resolve final numeric entity_id per path (stable scan order) ---
    sorted_docs = sorted(documents, key=lambda d: document_rel_posix(d, ksfs_r))
    decl_samples: list[str | None] = []
    work_items: list[tuple[SourceDocument, str, str | None]] = []
    for doc in sorted_docs:
        rel = document_rel_posix(doc, ksfs_r)
        headers, _body = split_front_matter(doc.text)
        proposed = extract_numeric_entity_id(headers, rel_posix=rel)
        decl_samples.append(proposed)
        work_items.append((doc, rel, proposed))

    counter = _max_numeric_from_declarations(decl_samples, hsi_max=hsi_max)

    final_id_by_rel: dict[str, str] = {}
    for doc, rel, proposed in work_items:
        stale_ids = [eid for eid, p in occupancy.items() if p == rel]
        for eid in stale_ids:
            del occupancy[eid]

        chosen: str | None = None
        if proposed is not None:
            owner = occupancy.get(proposed)
            if owner is None or owner == rel:
                chosen = proposed
        if chosen is None:
            if proposed is not None:
                conflicts += 1
            new_id, counter = _next_numeric_id(counter=counter, occupancy=occupancy)
            chosen = new_id
            id_allocated += 1
        occupancy[chosen] = rel
        final_id_by_rel[rel] = chosen

    # --- Phase 2: front matter writeback ---
    for doc in sorted_docs:
        rel = document_rel_posix(doc, ksfs_r)
        final_id = final_id_by_rel[rel]
        new_text, changed = ensure_front_matter_id(doc.path.read_text(encoding="utf-8"), final_id)
        if changed:
            doc.path.write_text(new_text, encoding="utf-8", newline="\n")
            fm_writebacks += 1

    # --- Phase 3: reload + HSI upsert ---
    documents2 = source.iter_documents()
    existing = hsi.fetch_by_paths([document_rel_posix(d, ksfs_r) for d in documents2])

    upserts: list[MetadataRecord] = []
    skipped = 0
    for doc in documents2:
        rel = document_rel_posix(doc, ksfs_r)
        headers, _body = split_front_matter(doc.text)
        numeric = extract_numeric_entity_id(headers, rel_posix=rel)
        entity_id = numeric or final_id_by_rel[rel]
        rec = _metadata_for_doc(doc, ksfs_root=ksfs_r, entity_id=entity_id)
        old = existing.get(rec.source_path)
        if (
            old is not None
            and old.content_hash == rec.content_hash
            and old.mtime_ns == rec.mtime_ns
            and old.entity_id == rec.entity_id
        ):
            skipped += 1
            continue
        upserts.append(rec)

    hsi.upsert(upserts)
    keep2 = frozenset(document_rel_posix(d, ksfs_r) for d in documents2)
    deleted = hsi.delete_not_in(keep2)

    return HdlSyncReport(
        documents_scanned=len(documents2),
        hsi_upserted=len(upserts),
        hsi_skipped_unchanged=skipped,
        hsi_deleted_stale=deleted,
        hsi_ids_allocated=id_allocated,
        fm_id_writebacks=fm_writebacks,
        hsi_id_conflicts_resolved=conflicts,
    )


def default_hsi_db_path(index_root: Path | None = None) -> Path:
    """Default SQLite path (``.index/.high-speed_index``)."""
    base = index_root if index_root is not None else Path(".index")
    return base / ".high-speed_index"
