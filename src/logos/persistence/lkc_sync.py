"""LKC: mirror normalized Markdown from KSFS into a local cache tree."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from logos.ports.knowledge_source import SourceDocument

from ._paths import to_posix_relative


@dataclass(frozen=True, slots=True)
class LkcSyncResult:
    written: tuple[str, ...]
    """Relative POSIX paths written or updated."""
    removed: tuple[str, ...]
    """Relative POSIX paths removed from LKC when prune=True."""


def sync_lkc_from_documents(
    *,
    ksfs_root: Path,
    lkc_root: Path,
    documents: list[SourceDocument],
    prune: bool = True,
) -> LkcSyncResult:
    """
    Write each document's normalized UTF-8 (LF) text under ``lkc_root``,
    preserving relative layout to ``ksfs_root``. Optionally remove LKC
    ``*.md`` files that no longer exist in the document set.
    """
    ksfs_r = ksfs_root.resolve()
    lkc_r = lkc_root.resolve()
    lkc_r.mkdir(parents=True, exist_ok=True)

    expected: set[str] = set()
    written: list[str] = []

    for doc in documents:
        rel = to_posix_relative(ksfs_r, doc.path)
        expected.add(rel)
        out_path = lkc_r / Path(rel)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = doc.text.encode("utf-8")
        prev: bytes | None = None
        if out_path.is_file():
            prev = out_path.read_bytes()
        if prev != payload:
            out_path.write_bytes(payload)
            written.append(rel)

    removed: list[str] = []
    if prune:
        for p in sorted(lkc_r.rglob("*.md")):
            if any(part.startswith(".") for part in p.parts):
                continue
            rel = to_posix_relative(lkc_r, p)
            if rel not in expected:
                p.unlink(missing_ok=True)
                removed.append(rel)
        _prune_empty_dirs(lkc_r)

    return LkcSyncResult(written=tuple(written), removed=tuple(removed))


def _prune_empty_dirs(root: Path) -> None:
    """Remove empty directories bottom-up under root (excluding root)."""
    root_r = root.resolve()
    changed = True
    while changed:
        changed = False
        for dirpath, _, _ in os.walk(root_r, topdown=False):
            p = Path(dirpath)
            try:
                if p.resolve() == root_r or not p.is_dir():
                    continue
                if any(p.iterdir()):
                    continue
                p.rmdir()
                changed = True
            except OSError:
                pass
