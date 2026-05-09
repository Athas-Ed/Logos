from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Normalized view of a file under KSFS / LKC."""

    path: Path
    text: str
    content_hash: str
    mtime_ns: int


@runtime_checkable
class KnowledgeSource(Protocol):
    """KSS: list and read narrative sources (KSFS → LKC in V0.1)."""

    def iter_documents(self) -> list[SourceDocument]:
        ...

    def read_document(self, relative_path: str) -> SourceDocument:
        ...
