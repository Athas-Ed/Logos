"""A8a：后端 KSFS→HSI→（可选 SVS/Chroma）→FusedRetrievalService 全链路 E2E。

- 使用 ``tmp_path`` 独立目录，不依赖仓库 ``resources/ksfs``、Electron 或 HTTP。
- 与 ``scripts/run_backend_stub.py`` 装配思路对齐：``SqliteMetadataIndex`` +
  ``FusedRetrievalService``（懒登记或 ``lazy_svs_state_db`` 触发 SVS 增量）。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from logos.infrastructure.retrieval.fused import FusedRetrievalService
from logos.persistence import SqliteMetadataIndex


class _Fixed512Embedder:
    """与 ``test_stream3_chroma_and_retrieval`` 一致：固定维向量，便于 Chroma 余弦召回。"""

    def embed(self, texts: list[str]) -> list[list[float]]:  # noqa: ANN001
        return [[0.03] * 512 for _ in texts]


class _NoopSemanticStore:
    """无 chromadb 时占位，融合检索仅走 HSI 分支。"""

    def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def query(self, query_embedding: list[float], top_k: int):  # noqa: ANN001
        return []


def test_e2e_cold_tmp_ksfs_lazy_hsi_then_fused_keyword(
    tmp_path: Path,
) -> None:
    """登记（首次 ``query`` 懒触发）→ HSI 关键词 → 融合检索断言；无向量库依赖。"""
    ksfs = tmp_path / "ksfs"
    index_root = tmp_path / ".index"
    hsi_db = index_root / ".high-speed_index"
    (ksfs / "lore").mkdir(parents=True)
    md = ksfs / "lore" / "amber_clock.md"
    md.write_text(
        "---\ntitle: 琥珀钟楼\n---\n\n# 设定\n\n钟楼齿轮在午夜校准。\n",
        encoding="utf-8",
    )

    meta = SqliteMetadataIndex(hsi_db)
    retrieval = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=_NoopSemanticStore(),
        embedder=_Fixed512Embedder(),
        lazy_hsi_ksfs_root=ksfs,
        lazy_hsi_db_path=hsi_db,
        lazy_svs_state_db=None,
    )
    cites = retrieval.query(text="琥珀钟楼", top_k=5)
    paths = {c.path for c in cites}
    assert "lore/amber_clock.md" in paths

    text = md.read_text(encoding="utf-8")
    assert re.search(r'id:\s*"\d+"', text)


@pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="未安装 chromadb，跳过 SVS→Chroma 全链路",
)
def test_e2e_tmp_ksfs_hsi_svs_chroma_fused_snippet(
    tmp_path: Path,
) -> None:
    """含 ``lazy_svs_state_db``：每次 ``query`` 前 SVS 增量；向量分支应带回正文片段。"""
    from logos.infrastructure.vector.chroma_store import ChromaSemanticStore

    ksfs = tmp_path / "ksfs"
    index_root = tmp_path / ".index"
    hsi_db = index_root / ".high-speed_index"
    svs_state_db = index_root / ".svs_chunk_index.sqlite"
    chroma_dir = index_root / ".vector_index"

    marker = "龙语石碑九号符文仅测E2E"
    (ksfs / "lore").mkdir(parents=True)
    md = ksfs / "lore" / "e2e_svs.md"
    md.write_text(
        f"---\ntitle: E2E SVS 文档\n---\n\n# 章节\n\n正文包含{marker}用于向量召回。\n",
        encoding="utf-8",
    )

    store = ChromaSemanticStore(
        persist_directory=str(chroma_dir),
        collection_name="ksfs_e2e_pipeline",
    )
    meta = SqliteMetadataIndex(hsi_db)
    retrieval = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=store,
        embedder=_Fixed512Embedder(),
        lazy_hsi_ksfs_root=ksfs,
        lazy_hsi_db_path=hsi_db,
        lazy_svs_state_db=svs_state_db,
    )
    cites = retrieval.query(text=marker, top_k=8)
    assert cites, "融合检索应至少返回一条命中"
    by_path = {c.path: c for c in cites}
    assert "lore/e2e_svs.md" in by_path
    hit = by_path["lore/e2e_svs.md"]
    assert marker in hit.snippet or marker in (hit.snippet.replace("…", ""))

    fm = md.read_text(encoding="utf-8")
    assert re.search(r'id:\s*"\d+"', fm)
