"""Scan KSFS tree and expose :class:`~logos.ports.knowledge_source.KnowledgeSource`."""

from __future__ import annotations

from pathlib import Path

from logos.ports.knowledge_source import SourceDocument

from ._hash import content_hash_hex, normalize_text_for_storage
from logos.paths import resolve_path_under_root, to_posix_relative


class FilesystemKnowledgeSource:
    """Scan a KSFS root for Markdown; paths are relative POSIX strings in HSI."""

    __slots__ = ("_root",)

    def __init__(self, ksfs_root: Path) -> None:
        self._root = ksfs_root.resolve()

    @property
    def ksfs_root(self) -> Path:
        return self._root

    def _load(self, path: Path) -> SourceDocument:
        raw = path.read_text(encoding="utf-8", errors="replace")
        normalized = normalize_text_for_storage(raw)
        st = path.stat()
        return SourceDocument(
            path=path,
            text=normalized,
            content_hash=content_hash_hex(normalized),
            mtime_ns=st.st_mtime_ns,
        )

    def iter_documents(self) -> list[SourceDocument]:
        if not self._root.is_dir():
            return []
        paths: list[Path] = []
        for p in sorted(self._root.rglob("*.md")):
            if any(part.startswith(".") for part in p.parts):
                continue
            paths.append(p)
        return [self._load(p) for p in paths]

    def read_document(self, relative_path: str) -> SourceDocument:
        path = resolve_path_under_root(self._root, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return self._load(path)


def document_rel_posix(source: SourceDocument, ksfs_root: Path) -> str:
    """Relative POSIX path from KSFS root for indexing."""
    return to_posix_relative(ksfs_root, source.path)
