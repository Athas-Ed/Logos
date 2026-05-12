"""将 KSFS 文档粗粒度写入 Chroma（每文件一块，便于本地开发检索）。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from logos.ports.embedding import TextEmbedder
from logos.ports.vector import SemanticStore

from ._front_matter import split_front_matter
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix


def reindex_ksfs_to_semantic_store(
    *,
    ksfs_root: Path,
    store: SemanticStore,
    embedder: TextEmbedder,
    max_body_chars: int = 12_000,
) -> int:
    """每 Markdown 文件嵌入正文（front matter 之后）一块；返回写入块数。"""
    root = ksfs_root.resolve()
    src = FilesystemKnowledgeSource(root)
    documents = src.iter_documents()
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, str]] = []

    for doc in documents:
        rel = document_rel_posix(doc, root)
        _, body = split_front_matter(doc.text)
        chunk = (body or doc.text).strip()
        if not chunk:
            continue
        chunk = chunk[:max_body_chars]
        digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()
        cid = f"ck_{digest[:40]}"
        ids.append(cid)
        texts.append(chunk)
        metadatas.append({"source_path": rel})

    if not ids:
        return 0
    embeddings = embedder.embed(texts)
    store.upsert_chunks(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)
    return len(ids)
