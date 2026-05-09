"""持久层 HDL 实现（KSS、HSI、与 SVS 衔接等）— Stream 2。"""

from __future__ import annotations

from .hdl_sync import HdlSyncReport, default_hsi_db_path, sync_ksfs_lkc_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .kss_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .lkc_sync import LkcSyncResult, sync_lkc_from_documents

__all__ = [
    "FilesystemKnowledgeSource",
    "HdlSyncReport",
    "LkcSyncResult",
    "SqliteMetadataIndex",
    "default_hsi_db_path",
    "document_rel_posix",
    "sync_lkc_from_documents",
    "sync_ksfs_lkc_hsi",
]
