"""持久层 HDL 实现（KSFS 扫描、HSI、与 SVS 衔接等）。"""

from __future__ import annotations

from ._hash import content_hash_hex, normalize_text_for_storage
from .hdl_sync import HdlSyncReport, default_hsi_db_path, sync_ksfs_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix

__all__ = [
    "FilesystemKnowledgeSource",
    "HdlSyncReport",
    "SqliteMetadataIndex",
    "content_hash_hex",
    "default_hsi_db_path",
    "document_rel_posix",
    "normalize_text_for_storage",
    "sync_ksfs_hsi",
]
