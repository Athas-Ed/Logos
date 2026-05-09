from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    """HSI（高速索引）一行记录的形状（后续里程碑可增字段）。"""

    entity_id: str
    title: str
    source_path: str
    content_hash: str
    mtime_ns: int


@runtime_checkable
class MetadataIndex(Protocol):
    """结构化元数据索引（例如 SQLite 实现的 HSI）。"""

    def upsert(self, records: list[MetadataRecord]) -> None:
        ...

    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        ...
