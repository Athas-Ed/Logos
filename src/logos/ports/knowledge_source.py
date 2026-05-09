from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """KSFS / LKC 下某一文件的规范化视图。"""

    path: Path
    text: str
    content_hash: str
    mtime_ns: int


@runtime_checkable
class KnowledgeSource(Protocol):
    """知识源服务（KSS）：枚举并读取叙事源文件（V0.1 中 KSFS → LKC）。"""

    def iter_documents(self) -> list[SourceDocument]:
        ...

    def read_document(self, relative_path: str) -> SourceDocument:
        ...
