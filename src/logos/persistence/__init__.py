"""持久层 HDL 实现（KSS、HSI、与 SVS 衔接等）— Stream 2。"""

from __future__ import annotations

from ._hash import content_hash_hex, normalize_text_for_storage
from .hdl_sync import HdlSyncReport, default_hsi_db_path, sync_ksfs_lkc_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .kss_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .lkc_sync import LkcSyncResult, sync_lkc_from_documents

__all__ = [
    "FilesystemKnowledgeSource",
    "HdlSyncReport",
    "LkcSyncResult",
    "SqliteMetadataIndex",
    "content_hash_hex",
    "default_hsi_db_path",
    "document_rel_posix",
    "normalize_text_for_storage",
    "sync_lkc_from_documents",
    "sync_ksfs_lkc_hsi",
]
