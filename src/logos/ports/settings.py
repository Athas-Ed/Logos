from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppSettings:
    """合并 defaults + local + 环境变量后的只读配置快照（Stream 1）。"""

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
