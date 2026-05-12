from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """KSFS 下某一 Markdown 文件的规范化视图（供索引与 HSI）。"""

    path: Path
    text: str
    content_hash: str
    mtime_ns: int


@runtime_checkable
class KnowledgeSource(Protocol):
    """枚举并读取 KSFS 源文件（叙事知识事实源）。"""

    def iter_documents(self) -> list[SourceDocument]:
        ...

    def read_document(self, relative_path: str) -> SourceDocument:
        ...
