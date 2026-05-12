"""Stream 3：Chroma 向量库与融合检索（可 mock，不强制加载大模型）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from logos.infrastructure.retrieval.fused import FusedRetrievalService
from logos.ports.metadata import MetadataRecord
from logos.ports.retrieval import Citation
from logos.ports.vector import VectorQueryHit


class _FixedEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * 512 for _ in texts]


class _MemVectorStore:
    def __init__(self, hits: list[VectorQueryHit]) -> None:
        self._hits = hits

    def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        return self._hits[:top_k]


class _MemMetadata:
    def __init__(self, rows: list[MetadataRecord]) -> None:
        self._rows = rows

    def upsert(self, records: list[MetadataRecord]) -> None:
        return None

    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        if prefix is None:
            return self._rows[:limit]
        p = prefix.replace("\\", "/")
        return [r for r in self._rows if r.source_path.startswith(p)][:limit]


def test_fused_retrieval_merges_vector_and_metadata() -> None:
    hits = [
        VectorQueryHit(
            chunk_id="c1",
            text="向量片段",
            score=0.9,
            source_path="a/b.md",
        )
    ]
    rows = [
        MetadataRecord(
            entity_id="e",
            title="关键词命中",
            source_path="c/other.md",
            content_hash="0" * 64,
            mtime_ns=1,
        )
    ]
    svc = FusedRetrievalService(
        metadata_index=_MemMetadata(rows),
        semantic_store=_MemVectorStore(hits),
        embedder=_FixedEmbedder(),
    )
    out = svc.query(text="关键词", top_k=8)
    paths = {c.path for c in out}
    assert "a/b.md" in paths
    assert "c/other.md" in paths
    assert all(isinstance(c, Citation) for c in out)


@pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="未安装 chromadb，跳过持久化向量集成测",
)
def test_chroma_semantic_store_roundtrip(tmp_path: Path) -> None:
    from logos.infrastructure.vector.chroma_store import ChromaSemanticStore

    persist = tmp_path / "chroma_persist"
    store = ChromaSemanticStore(
        persist_directory=str(persist),
        collection_name="pytest_ksfs",
    )
    emb = [[0.02] * 512]
    store.upsert_chunks(
        ids=["chunk-1"],
        texts=["示例正文用于检索"],
        embeddings=emb,
        metadatas=[{"source_path": "notes/demo.md"}],
    )
    got = store.query(emb[0], top_k=3)
    assert len(got) >= 1
    assert got[0].source_path == "notes/demo.md"


def test_fused_hsi_matches_chinese_title_with_extra_token() -> None:
    """「山巅城堡 设定」类查询应命中标题「山巅城堡」（HSI 分支）。"""
    from logos.infrastructure.retrieval import fused as fused_mod

    rows = [
        MetadataRecord(
            entity_id="x",
            title="山巅城堡",
            source_path="Test/山巅城堡.md",
            content_hash="0" * 64,
            mtime_ns=1,
        )
    ]
    svc = FusedRetrievalService(
        metadata_index=_MemMetadata(rows),
        semantic_store=_MemVectorStore([]),
        embedder=_FixedEmbedder(),
    )
    out = svc.query(text="山巅城堡 设定", top_k=5)
    assert len(out) >= 1
    assert out[0].path == "Test/山巅城堡.md"
    assert fused_mod._hsi_keyword_score("山巅城堡 设定", rows[0]) > 0


@pytest.mark.slow
def test_bge_embedder_local_model_smoke() -> None:
    """本机需已放置 models/tooling/embeddings/bge-small-zh-v1.5 且安装 sentence-transformers。"""
    pytest.importorskip("sentence_transformers")
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    model_dir = root / "models" / "tooling" / "embeddings" / "bge-small-zh-v1.5"
    if not model_dir.is_dir():
        pytest.skip("未找到本地 BGE 权重目录，跳过")

    from logos.infrastructure.embeddings.bge_small_zh import BgeSmallZhEmbedder

    emb = BgeSmallZhEmbedder(str(model_dir))
    vecs = emb.embed(["测试句子", "第二句"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 512
