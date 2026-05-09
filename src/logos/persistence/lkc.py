"""LKC: mirror normalized Markdown from KSS into a local cache tree."""

from __future__ import annotations

from pathlib import Path

from logos.ports.knowledge_source import SourceDocument

from logos.persistence.kss_filesystem import FilesystemKnowledgeSource, document_rel_posix


def sync_ksfs_to_lkc(
    kss: FilesystemKnowledgeSource,
    lkc_root: Path,
    *,
    prune: bool = True,
) -> tuple[set[str], int]:
    """
    Write each KSS document under ``lkc_root`` preserving relative paths (POSIX).

    Returns ``(relative_posix_paths_written, pruned_file_count)``.
    """
    lkc_r = lkc_root.resolve()
    docs = kss.iter_documents()
    written: set[str] = set()
    for doc in docs:
        rel = document_rel_posix(doc, kss.ksfs_root)
        target = lkc_r.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc.text, encoding="utf-8", newline="\n")
        written.add(rel)

    pruned = 0
    if prune and lkc_r.is_dir():
        for p in sorted(lkc_r.rglob("*.md"), reverse=True):
            rel = p.resolve().relative_to(lkc_r).as_posix()
            if rel not in written:
                p.unlink(missing_ok=True)
                pruned += 1
        # remove empty directories (best-effort)
        for d in sorted({p.parent for p in lkc_r.rglob("*") if p.is_dir()}, key=lambda x: len(x.parts), reverse=True):
            if d == lkc_r:
                continue
            try:
                next(d.iterdir())
            except StopIteration:
                d.rmdir()
            except OSError:
                pass

    return written, pruned
