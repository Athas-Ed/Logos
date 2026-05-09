from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Read-only snapshot after merging defaults + local + env (Stream 1)."""

    workspace_root: str
    example_ksfs_root: str
    index_root: str
    logs_root: str
    hsi_sqlite_path: str
    chroma_persist_directory: str
    chroma_collection: str
    embedding_provider: str
    embedding_model_path: str
    operating_mode: str = "author"
