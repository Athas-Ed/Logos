"""持久层 HDL 实现（KSFS 扫描、HSI、与 SVS 衔接等）。"""

from __future__ import annotations

from ._hash import content_hash_hex, normalize_text_for_storage
from .chroma_bootstrap import (
    SvsSyncReport,
    default_svs_state_db_path,
    reindex_ksfs_to_semantic_store,
    sync_ksfs_svs_incremental,
)
from .hdl_sync import HdlSyncReport, default_hsi_db_path, sync_ksfs_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .registration import ensure_ksfs_hsi_registered
from .svs_chunking import (
    ChunkRecord,
    build_chunk_records,
    chunk_markdown_body,
    compute_chunk_id,
    normalize_for_substring_match,
    tokenize,
)

__all__ = [
    "ChunkRecord",
    "FilesystemKnowledgeSource",
    "HdlSyncReport",
    "SqliteMetadataIndex",
    "SvsSyncReport",
    "build_chunk_records",
    "chunk_markdown_body",
    "compute_chunk_id",
    "content_hash_hex",
    "default_hsi_db_path",
    "default_svs_state_db_path",
    "document_rel_posix",
    "ensure_ksfs_hsi_registered",
    "normalize_for_substring_match",
    "normalize_text_for_storage",
    "reindex_ksfs_to_semantic_store",
    "sync_ksfs_hsi",
    "sync_ksfs_svs_incremental",
    "tokenize",
]
