from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    """HSI row shape (fields may grow in later milestones)."""

    entity_id: str
    title: str
    source_path: str
    content_hash: str
    mtime_ns: int


@runtime_checkable
class MetadataIndex(Protocol):
    """Structured index (e.g. SQLite HSI)."""

    def upsert(self, records: list[MetadataRecord]) -> None:
        ...

    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        ...
