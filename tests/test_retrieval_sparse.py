"""R1：Sparse FTS5 索引单测 + 融合回归。"""

from __future__ import annotations

from pathlib import Path

import pytest

from logos.infrastructure.retrieval.fused import FusedRetrievalService
from logos.persistence import (
    IndexSync,
    SqliteMetadataIndex,
    SqliteSparseIndex,
    build_chunk_records,
    sync_ksfs_hsi,
    sync_ksfs_indexes,
)


class _Fixed512Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.03] * 512 for _ in texts]


class _NoopSemanticStore:
    def upsert_chunks(self, **kwargs) -> None:
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def query(self, query_embedding: list[float], top_k: int):
        return []


# ── SqliteSparseIndex unit tests ────────────────────────────────────────

def test_sparse_upsert_and_search(tmp_path: Path) -> None:
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1", "c2"],
        entity_ids=["e1", "e1"],
        source_paths=["lore/amber_clock.md", "lore/amber_clock.md"],
        texts=["钟楼齿轮在午夜校准", "琥珀钟楼高四十七米"],
        norm_texts=["钟楼齿轮在午夜校准", "琥珀钟楼高四十七米"],
    )
    hits = idx.search("午夜校准", top_k=5)
    assert len(hits) >= 1
    assert hits[0].chunk_id == "c1"
    assert hits[0].score > 0


def test_sparse_search_no_match(tmp_path: Path) -> None:
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1"],
        entity_ids=["e1"],
        source_paths=["doc.md"],
        texts=["测试正文"],
        norm_texts=["测试正文"],
    )
    hits = idx.search("不存在的词语", top_k=5)
    assert len(hits) == 0


def test_sparse_delete_ids(tmp_path: Path) -> None:
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1", "c2"],
        entity_ids=["e1", "e1"],
        source_paths=["a.md", "b.md"],
        texts=["alpha", "beta"],
        norm_texts=["alpha", "beta"],
    )
    idx.delete_ids(["c1"])
    hits = idx.search("alpha", top_k=5)
    assert len(hits) == 0
    hits2 = idx.search("beta", top_k=5)
    assert len(hits2) == 1


def test_sparse_delete_by_paths(tmp_path: Path) -> None:
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1", "c2"],
        entity_ids=["e1", "e1"],
        source_paths=["a.md", "a.md"],
        texts=["正文一", "正文二"],
        norm_texts=["正文一", "正文二"],
    )
    idx.delete_by_paths(["a.md"])
    hits = idx.search("正文", top_k=5)
    assert len(hits) == 0


def test_sparse_chinese_phrase_search(tmp_path: Path) -> None:
    """中文短语「九号符文」应在 FTS5 中精确命中。"""
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1"],
        entity_ids=["e1"],
        source_paths=["lore/rune_nine.md"],
        texts=["九号符文是远古符文体系中最为神秘的符号"],
        norm_texts=["九号符文是远古符文体系中最为神秘的符号"],
    )
    hits = idx.search("九号符文", top_k=5)
    assert len(hits) == 1
    assert "九号符文" in hits[0].text


def test_sparse_mixed_language(tmp_path: Path) -> None:
    """中文 + ASCII 混排的搜索。"""
    idx = SqliteSparseIndex(tmp_path / "sparse.db")
    idx.upsert_chunks(
        chunk_ids=["c1"],
        entity_ids=["e1"],
        source_paths=["doc.md"],
        texts=["bge-small-zh 模型用于 embedding"],
        norm_texts=["bge-small-zh 模型用于 embedding"],
    )
    hits = idx.search("bge-small-zh embedding", top_k=5)
    assert len(hits) == 1


# ── sync_ksfs_indexes（Sparse 分支）tests ──────────────────────────────

def test_sparse_sync_first_run(tmp_path: Path) -> None:
    """首次同步：应索引所有文档的 chunk。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "lore").mkdir(parents=True)
    (ksfs / "lore" / "doc.md").write_text(
        "---\ntitle: 测试文档\n---\n\n# 第一章\n\n琥珀钟楼的齿轮在午夜校准。\n",
        encoding="utf-8",
    )
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    sparse_db = tmp_path / ".index" / ".sparse_fts.sqlite"
    sparse = SqliteSparseIndex(sparse_db)

    sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi_db)
    rep = sync_ksfs_indexes(
        ksfs_root=ksfs,
        hsi_db=hsi_db,
        sparse_index=sparse,
        sparse_db=sparse_db,
    )
    assert rep.sparse_documents_indexed >= 1
    assert rep.sparse_chunks_upserted >= 1
    assert rep.sparse_documents_skipped_unchanged == 0
    assert rep.chunks_deleted_stale == 0

    hits = sparse.search("琥珀钟楼", top_k=5)
    assert len(hits) >= 1


def test_sparse_sync_second_run_skips(tmp_path: Path) -> None:
    """第二次同步无变更时应全部跳过。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "doc").mkdir(parents=True)
    (ksfs / "doc" / "n.md").write_text(
        "---\n---\n\n# T\n\nhello world 正文\n", encoding="utf-8",
    )
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    sparse_db = tmp_path / ".index" / ".sparse_fts.sqlite"
    sparse = SqliteSparseIndex(sparse_db)

    sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi_db)
    r1 = sync_ksfs_indexes(
        ksfs_root=ksfs, hsi_db=hsi_db, sparse_index=sparse, sparse_db=sparse_db,
    )
    assert r1.sparse_chunks_upserted >= 1
    u1 = r1.sparse_chunks_upserted

    r2 = sync_ksfs_indexes(
        ksfs_root=ksfs, hsi_db=hsi_db, sparse_index=sparse, sparse_db=sparse_db,
    )
    assert r2.sparse_documents_skipped_unchanged >= 1
    assert r2.sparse_chunks_upserted == 0
    assert r2.chunks_deleted_stale == 0


def test_sparse_sync_detects_content_change(tmp_path: Path) -> None:
    """修改正文后第二次同步应更新索引。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "doc").mkdir(parents=True)
    md = ksfs / "doc" / "n.md"
    md.write_text("---\n---\n\n# T\n\nv1 旧内容\n", encoding="utf-8")
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    sparse_db = tmp_path / ".index" / ".sparse_fts.sqlite"
    sparse = SqliteSparseIndex(sparse_db)

    sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi_db)
    sync_ksfs_indexes(
        ksfs_root=ksfs, hsi_db=hsi_db, sparse_index=sparse, sparse_db=sparse_db,
    )

    md.write_text("---\n---\n\n# T\n\nv2 新内容新关键词\n", encoding="utf-8")
    sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi_db)
    r2 = sync_ksfs_indexes(
        ksfs_root=ksfs, hsi_db=hsi_db, sparse_index=sparse, sparse_db=sparse_db,
    )
    assert r2.sparse_chunks_upserted >= 1
    hits = sparse.search("新关键词", top_k=5)
    assert len(hits) >= 1


# ── FusedRetrievalService + sparse integration ──────────────────────────

def test_fused_with_sparse_returns_fts_hits(tmp_path: Path) -> None:
    """Sparse 分支加入后，正文关键词不在 title 也可召回。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "test").mkdir(parents=True)
    (ksfs / "test" / "doc.md").write_text(
        "---\ntitle: 标题无关键词\n---\n\n# 正文\n\n专有名词琥珀钟楼仅在正文出现。\n",
        encoding="utf-8",
    )
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    sparse_db = tmp_path / ".index" / ".sparse_fts.sqlite"
    meta = SqliteMetadataIndex(hsi_db)
    sparse = SqliteSparseIndex(sparse_db)

    svc = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=_NoopSemanticStore(),
        embedder=_Fixed512Embedder(),
        sparse_index=sparse,
        index_sync=IndexSync(
            ksfs_root=ksfs,
            hsi_db=hsi_db,
            sparse_index=sparse,
            sparse_db=sparse_db,
        ),
    )
    cites = svc.query(text="琥珀钟楼", top_k=5)
    paths = {c.path for c in cites}
    assert "test/doc.md" in paths, (
        f"sparse 分支应通过正文关键词召回，实际得到: {paths}"
    )


def test_fused_sparse_no_chroma_still_works(tmp_path: Path) -> None:
    """无 Chroma（_NoopSemanticStore）时，sparse + HSI 仍可返回结果。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "lore").mkdir(parents=True)
    (ksfs / "lore" / "amber.md").write_text(
        "---\ntitle: 钟楼\n---\n\n# 设定\n\n齿轮在午夜校准。\n",
        encoding="utf-8",
    )
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    sparse_db = tmp_path / ".index" / ".sparse_fts.sqlite"
    meta = SqliteMetadataIndex(hsi_db)
    sparse = SqliteSparseIndex(sparse_db)

    svc = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=_NoopSemanticStore(),
        embedder=_Fixed512Embedder(),
        sparse_index=sparse,
        index_sync=IndexSync(
            ksfs_root=ksfs,
            hsi_db=hsi_db,
            sparse_index=sparse,
            sparse_db=sparse_db,
        ),
    )
    cites = svc.query(text="午夜校准", top_k=5)
    assert len(cites) >= 1, "无 Chroma 时 sparse+HSI 仍应命中"
    # HSI 分支会因为 title "钟楼" 匹配，sparse 因为正文 "午夜校准" 匹配


def test_fused_sparse_disabled_falls_back(tmp_path: Path) -> None:
    """sparse_index=None 时退化为原 HSI+SVS 行为。"""
    ksfs = tmp_path / "ksfs"
    (ksfs / "test").mkdir(parents=True)
    (ksfs / "test" / "doc.md").write_text(
        "---\ntitle: 可见标题\n---\n\n正文内容关键词在标题可匹配。\n",
        encoding="utf-8",
    )
    hsi_db = tmp_path / ".index" / ".high-speed_index"
    meta = SqliteMetadataIndex(hsi_db)

    svc = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=_NoopSemanticStore(),
        embedder=_Fixed512Embedder(),
        sparse_index=None,
        index_sync=IndexSync(ksfs_root=ksfs, hsi_db=hsi_db),
    )
    cites = svc.query(text="可见标题", top_k=5)
    assert len(cites) >= 1
