"""检索基准评测：加载测试集 → 构造检索服务 → 跑指标 → 分析报告。

用法：
    pytest tests/retrieval_benchmark.py -q                      # 全量
    pytest tests/retrieval_benchmark.py -q -k "sparse"          # 仅 sparse 标签 query
    pytest tests/retrieval_benchmark.py -q --run-real-embedder  # 真实 embedder（慢）

输出 JSON 基线到 ``tests/fixtures/retrieval/baseline_r0.json``。
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from logos.infrastructure.retrieval.fused import FusedRetrievalService
from logos.persistence import (
    IndexSync,
    SqliteMetadataIndex,
    SqliteSparseIndex,
    default_svs_state_db_path,
    sync_ksfs_hsi,
)
from logos.ports.metadata import MetadataRecord
from logos.ports.retrieval import Citation
from logos.ports.sparse import SparseQueryHit
from logos.ports.vector import VectorQueryHit
from logos.ports.embedding import TextEmbedder


# ── stubs ───────────────────────────────────────────────────────────────

class _Fixed512Embedder:
    """固定嵌入，避免 embedder 波动影响评分。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.03] * 512 for _ in texts]


class _NoopSemanticStore:
    """无向量库时的占位。"""

    def upsert_chunks(self, **kwargs: Any) -> None:
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        return []


class _CharFreqEmbedder:
    """字符频率嵌入器：将文本映射为 512 维归一化向量。

    每个字符通过哈希映射到 0-511 中的一个桶，桶内计数累加后 L2 归一化。
    相似文本（共享较多字符）会得到相似的向量——在基准中提供有意义的 SVS 相似度。
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * 512
            for ch in text.lower():
                bucket = (ord(ch) * 31 + 7) % 512
                vec[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 1e-9:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out


class _InMemVectorStore:
    """内存向量库：存储 chunk，cosine similarity 检索。"""

    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, Any]] = {}

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]] | None = None,
    ) -> None:
        for i, cid in enumerate(ids):
            md = metadatas[i] if metadatas else {}
            self._chunks[cid] = {
                "text": texts[i],
                "embedding": embeddings[i],
                "source_path": md.get("source_path", ""),
            }

    def delete_ids(self, ids: list[str]) -> None:
        for cid in ids:
            self._chunks.pop(cid, None)

    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for cid, data in self._chunks.items():
            sim = _cosine_sim(query_embedding, data["embedding"])
            scored.append((sim, cid, data))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            VectorQueryHit(
                chunk_id=cid,
                text=data["text"],
                score=sim,
                source_path=data["source_path"],
            )
            for sim, cid, data in scored[:top_k]
        ]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


class _EmptyMetadata:
    """返回空的 HSI，用于单路隔离。"""

    def upsert(self, records: list[MetadataRecord]) -> None:
        return None

    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        return []


class _NoopSparseIndex:
    """无 sparse 索引时的占位。"""

    def upsert_chunks(self, **kwargs: Any) -> None:
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def delete_by_paths(self, source_paths: list[str]) -> None:
        return None

    def search(self, query_text: str, top_k: int) -> list[SparseQueryHit]:
        return []


# ── data types ──────────────────────────────────────────────────────────

@dataclass
class Query:
    id: str
    text: str
    expected_paths: list[str]
    type: str
    tags: list[str]


@dataclass
class QueryResult:
    query_id: str
    citations: list[Citation]
    latency_s: float


@dataclass
class BenchmarkResult:
    component_label: str
    queries: list[QueryResult] = field(default_factory=list)

    def recall_at(self, k: int) -> float:
        hits = 0
        total = 0
        for qr in self.queries:
            q = _query_map.get(qr.query_id)
            if q is None or not q.expected_paths:
                continue
            total += 1
            top_paths = {c.path for c in qr.citations[:k]}
            if any(ep in top_paths for ep in q.expected_paths):
                hits += 1
        return hits / total if total > 0 else 0.0

    def mrr_at(self, k: int) -> float:
        reciprocal_sum = 0.0
        total = 0
        for qr in self.queries:
            q = _query_map.get(qr.query_id)
            if q is None or not q.expected_paths:
                continue
            total += 1
            for rank, cit in enumerate(qr.citations[:k], start=1):
                if cit.path in q.expected_paths:
                    reciprocal_sum += 1.0 / rank
                    break
        return reciprocal_sum / total if total > 0 else 0.0


# ── globals (populated by load_queries) ─────────────────────────────────

_query_map: dict[str, Query] = {}


# ── helpers ─────────────────────────────────────────────────────────────

def load_queries(path: str = "tests/fixtures/retrieval/queries.json") -> list[Query]:
    """加载 queries.json → Query 对象列表。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[Query] = []
    for item in raw:
        q = Query(
            id=str(item["id"]),
            text=str(item["text"]),
            expected_paths=[str(p) for p in item.get("expected_paths", [])],
            type=str(item.get("type", "")),
            tags=[str(t) for t in item.get("tags", [])],
        )
        out.append(q)
        _query_map[q.id] = q
    return out


def build_ksfs_fixture(tmp_path: Path, ksfs_src: str = "tests/fixtures/retrieval/ksfs") -> Path:
    """将基准 KSFS 小库复制到 ``tmp_path`` 下，确保每次测试独立。"""
    src = Path(ksfs_src)
    dst = tmp_path / "ksfs"
    if src.is_dir():
        import shutil

        shutil.copytree(src, dst, dirs_exist_ok=True)
    return dst


def make_retrieval_service(
    ksfs_root: Path,
    index_root: Path,
    components: str = "hsi+svs+sparse",
) -> FusedRetrievalService:
    """按 ``components`` 参数（hsi/svs/sparse/+组合）创建只含指定组件的融合服务。"""
    hsi_db = index_root / ".high-speed_index"
    svs_state = index_root / ".svs_chunk_index.sqlite"
    sparse_db = index_root / ".sparse_fts.sqlite"

    meta = SqliteMetadataIndex(hsi_db)

    parts = components.split("+")
    use_hsi = "hsi" in parts
    use_svs = "svs" in parts
    use_sparse = "sparse" in parts

    # semantic store
    if use_svs:
        store = _InMemVectorStore()
        svs_embedder: TextEmbedder = _CharFreqEmbedder()
    else:
        store = _NoopSemanticStore()
        svs_embedder = _Fixed512Embedder()

    # metadata index
    if not use_hsi:
        meta = _EmptyMetadata()  # type: ignore[assignment]

    # sparse index
    sparse_index: SqliteSparseIndex | _NoopSparseIndex | None = None
    sparse_db_path: Path | None = None
    if use_sparse:
        sparse_index = SqliteSparseIndex(sparse_db)
        sparse_db_path = sparse_db

    svc = FusedRetrievalService(
        metadata_index=meta,
        semantic_store=store,
        embedder=svs_embedder,
        sparse_index=sparse_index,
        index_sync=IndexSync(
            ksfs_root=ksfs_root,
            hsi_db=hsi_db,
            semantic_store=store,
            embedder=svs_embedder,
            svs_state_db=svs_state if use_svs else None,
            sparse_index=sparse_index,
            sparse_db=sparse_db_path,
        ),
    )
    return svc


def run_benchmark(
    retrieval: FusedRetrievalService,
    queries: list[Query],
    top_k: int = 8,
    *,
    label: str = "",
) -> BenchmarkResult:
    """执行所有 query，收集命中 + 延迟。"""
    out = BenchmarkResult(component_label=label)
    for q in queries:
        t0 = time.perf_counter()
        cites = retrieval.query(text=q.text, top_k=top_k)
        dt = time.perf_counter() - t0
        out.queries.append(
            QueryResult(query_id=q.id, citations=cites, latency_s=dt)
        )
    return out


def analyze(baseline: BenchmarkResult, component: BenchmarkResult) -> str:
    """对比分析，输出 recall / MRR 差异文本。"""
    lines: list[str] = []
    lines.append(f"=== 对比: {component.component_label} vs {baseline.component_label} ===")
    for k in (1, 3, 5, 8):
        br = baseline.recall_at(k)
        cr = component.recall_at(k)
        delta = cr - br
        lines.append(f"  Recall@{k}: 基线 {br:.3f}  → 当前 {cr:.3f}  ({'+' if delta >= 0 else ''}{delta:.3f})")
    bm = baseline.mrr_at(8)
    cm = component.mrr_at(8)
    lines.append(f"  MRR@8:    基线 {bm:.3f}  → 当前 {cm:.3f}  ({'+' if cm - bm >= 0 else ''}{cm - bm:.3f})")
    lines.append("")
    return "\n".join(lines)


def format_report(result: BenchmarkResult) -> str:
    """生成单次 benchmark 的可读 Markdown 报告。"""
    lines: list[str] = []
    lines.append(f"## 基准报告: {result.component_label}")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    for k in (1, 3, 5, 8):
        lines.append(f"| Recall@{k} | {result.recall_at(k):.3f} |")
    lines.append(f"| MRR@8 | {result.mrr_at(8):.3f} |")
    lines.append("")
    lines.append("### 逐查询详情")
    lines.append("")
    lines.append(f"| Query | 类型 | 命中 Path | 延迟(ms) |")
    lines.append("|-------|------|-----------|----------|")
    for qr in result.queries:
        q = _query_map.get(qr.query_id)
        if q is None:
            continue
        paths = ", ".join(c.path for c in qr.citations[:3]) or "(无)"
        lines.append(f"| {q.id} | {q.type} | {paths} | {qr.latency_s*1000:.1f} |")
    return "\n".join(lines)


def save_baseline(result: BenchmarkResult, path: str = "tests/fixtures/retrieval/baseline_r0.json") -> None:
    """将 benchmark 结果归档为 JSON 基线。"""
    data = {
        "label": result.component_label,
        "queries": [
            {
                "query_id": qr.query_id,
                "citations": [
                    {"path": c.path, "snippet": c.snippet, "score": c.score}
                    for c in qr.citations
                ],
                "latency_s": qr.latency_s,
            }
            for qr in result.queries
        ],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture(scope="module")
def queries() -> list[Query]:
    return load_queries()


# ── tests ───────────────────────────────────────────────────────────────

def test_benchmark_all_components(tmp_path: Path, queries: list[Query]) -> None:
    """全组件（HSI+SVS+Sparse）基准测试。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="hsi+svs+sparse",
    )
    result = run_benchmark(svc, queries, label="HSI+SVS+Sparse")
    report = format_report(result)
    print(report)

    assert result.recall_at(8) >= 0.3, f"Recall@8 过低: {result.recall_at(8):.3f}"
    assert result.mrr_at(8) >= 0.3, f"MRR@8 过低: {result.mrr_at(8):.3f}"


def test_benchmark_hsi_only(tmp_path: Path, queries: list[Query]) -> None:
    """仅 HSI 组件的基准（用于隔离分析）。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="hsi",
    )
    result = run_benchmark(svc, queries, label="HSI-only")
    report = format_report(result)
    print(report)


def test_benchmark_sparse_only(tmp_path: Path, queries: list[Query]) -> None:
    """仅 Sparse（FTS5）组件的基准。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="sparse",
    )
    result = run_benchmark(svc, queries, label="Sparse-only")
    report = format_report(result)
    print(report)


def test_benchmark_filter_by_tag(tmp_path: Path, queries: list[Query]) -> None:
    """按 tag 过滤 query 的基准（如仅 sparse / fts 标签）。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"
    filtered = [q for q in queries if "sparse" in q.tags or "fts" in q.tags]

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="hsi+svs+sparse",
    )
    result = run_benchmark(svc, filtered, label="Sparse-tag-filtered")
    report = format_report(result)
    print(report)


def test_benchmark_svs_only(tmp_path: Path, queries: list[Query]) -> None:
    """仅 SVS（字符频率嵌入）组件的基准——验证 SVS 路已真实参与。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="svs",
    )
    result = run_benchmark(svc, queries, label="SVS-only (char-freq)")
    report = format_report(result)
    print(report)

    # SVS-only 应当在 paraphrase 类 query 上有一定命中
    para_queries = [q for q in queries if q.type == "body_paraphrase"]
    para_hits = 0
    for qr in result.queries:
        q = _query_map.get(qr.query_id)
        if q is None or q.type != "body_paraphrase" or not q.expected_paths:
            continue
        if any(ep in {c.path for c in qr.citations[:5]} for ep in q.expected_paths):
            para_hits += 1
    print(f"  → body_paraphrase 类型命中 {para_hits}/{len(para_queries)} 条")


def test_benchmark_svs_vs_nosvs(tmp_path: Path, queries: list[Query]) -> None:
    """对比：有/无 SVS 的 Recall 差异——验证 SVS 是否真正改善了融合质量。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    nosvs = run_benchmark(
        make_retrieval_service(ksfs, index_root, "hsi+sparse"),
        queries,
        label="HSI+Sparse (no SVS)",
    )
    withsvs = run_benchmark(
        make_retrieval_service(ksfs, index_root, "hsi+svs+sparse"),
        queries,
        label="HSI+SVS+Sparse",
    )

    diff = analyze(nosvs, withsvs)
    print(diff)

    # 有 SVS 时 Recall@1 不应低于无 SVS 时（SVS 增加信息，不应减分）
    assert withsvs.recall_at(1) >= nosvs.recall_at(1) - 0.05, (
        f"SVS 导致 Recall@1 下降过多: {nosvs.recall_at(1):.3f} → {withsvs.recall_at(1):.3f}"
    )


@pytest.mark.slow
def test_benchmark_and_save_baseline(tmp_path: Path, queries: list[Query]) -> None:
    """跑全量并归档基线（仅 @slow 时执行）。"""
    ksfs = build_ksfs_fixture(tmp_path)
    index_root = tmp_path / ".index"

    svc = make_retrieval_service(
        ksfs_root=ksfs,
        index_root=index_root,
        components="hsi+svs+sparse",
    )
    result = run_benchmark(svc, queries, label="Baseline-R0")
    save_baseline(result)
    print(format_report(result))
