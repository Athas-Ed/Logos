"""FTS5 实现的 SparseIndex：chunk 级增量同步与检索。

与 ``chroma_bootstrap.sync_ksfs_svs_incremental`` 平行设计，复用同一 HSI 变更检测
和 ``svs_chunking.build_chunk_records`` / ``norm_text``。
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from logos.ports.sparse import SparseIndex, SparseQueryHit

from ._front_matter import split_front_matter
from .hdl_sync import sync_ksfs_hsi
from .hsi_sqlite import SqliteMetadataIndex
from .ksfs_filesystem import FilesystemKnowledgeSource, document_rel_posix
from .svs_chunking import build_chunk_records, compute_chunk_id


# ── CJK tokenization for FTS5 ──────────────────────────────────────────

#: 匹配连续 CJK 字符的序列
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+")


def _cjk_space(text: str) -> str:
    """在 CJK 字符之间插入空格，使 FTS5 unicode61 tokenizer 可逐字索引。

    ``钟楼齿轮在午夜校准`` → ``钟 楼 齿 轮 在 午 夜 校 准``
    非 CJK 部分（ASCII 数字等）保持原样，其内部空白不变。
    """
    return _CJK_RE.sub(lambda m: " ".join(m.group()), text)


# ── schema ──────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sparse_sync_state (
    source_path TEXT NOT NULL PRIMARY KEY,
    entity_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    chunk_ids_json TEXT NOT NULL
);
"""

_FTS5_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS sparse_fts USING fts5(
    chunk_id UNINDEXED,
    entity_id UNINDEXED,
    source_path UNINDEXED,
    raw_text UNINDEXED,
    search_text,
    tokenize='unicode61'
);
"""


# ── reports ─────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SparseSyncReport:
    """``sync_ksfs_sparse_incremental`` 摘要。"""

    hsi_documents_scanned: int
    documents_indexed: int
    documents_skipped_unchanged: int
    chunks_upserted: int
    chunks_deleted_stale: int


# ── SQLite-backed SparseIndex ───────────────────────────────────────────

class SqliteSparseIndex:
    """FTS5 全文索引实现，单个 SQLite 库容纳 FTS5 表 + 同步状态表。"""

    __slots__ = ("_path",)

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    @property
    def db_path(self) -> Path:
        return self._path

    # -- internal helpers ------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._path, timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=DELETE")
        con.executescript(_SCHEMA)
        # FTS5 CREATE VIRTUAL TABLE 必须在单独 exec 中，不能混 execscript
        try:
            con.execute("SELECT count(*) FROM sparse_fts")
        except sqlite3.OperationalError:
            con.executescript(_FTS5_SCHEMA)
        return con

    # -- SparseIndex protocol --------------------------------------------

    def upsert_chunks(
        self,
        *,
        chunk_ids: list[str],
        entity_ids: list[str],
        source_paths: list[str],
        texts: list[str],
        norm_texts: list[str],
    ) -> None:
        """批量 upsert 到 FTS5 表。

        存入时 ``search_text`` 列使用 ``_cjk_space`` 预处理（CJK 字间插空格），
        以便 ``unicode61`` tokenizer 能逐字索引。
        """
        if not chunk_ids:
            return
        search_texts = [_cjk_space(nt) for nt in norm_texts]
        with closing(self._connect()) as con:
            con.executemany(
                """INSERT OR REPLACE INTO sparse_fts
                       (chunk_id, entity_id, source_path, raw_text, search_text)
                   VALUES (?, ?, ?, ?, ?)""",
                list(
                    zip(
                        chunk_ids,
                        entity_ids,
                        source_paths,
                        texts,
                        search_texts,
                        strict=True,
                    )
                ),
            )
            con.commit()

    def delete_ids(self, ids: list[str]) -> None:
        """按 ``chunk_id`` 批量删除。"""
        if not ids:
            return
        with closing(self._connect()) as con:
            for cid in ids:
                con.execute("DELETE FROM sparse_fts WHERE chunk_id = ?", (cid,))
            con.commit()

    def delete_by_paths(self, source_paths: list[str]) -> None:
        """按 ``source_path`` 批量删除。"""
        if not source_paths:
            return
        with closing(self._connect()) as con:
            for sp in source_paths:
                con.execute("DELETE FROM sparse_fts WHERE source_path = ?", (sp,))
            con.commit()

    def search(self, query_text: str, top_k: int) -> list[SparseQueryHit]:
        """FTS5 搜索。

        对 query 做 ``_cjk_space`` 预处理后构造 FTS5 MATCH 查询，
        在 ``search_text`` 列上匹配，取 BM25 排序前 top_k。
        """
        fts_q = _fts_query(query_text)
        if not fts_q:
            return []
        with closing(self._connect()) as con:
            cur = con.execute(
                """SELECT chunk_id, entity_id, source_path, raw_text, search_text, rank
                   FROM sparse_fts
                   WHERE sparse_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_q, max(top_k, 1)),
            )
            rows = cur.fetchall()
        return [
            SparseQueryHit(
                chunk_id=str(r["chunk_id"]),
                text=str(r["raw_text"]),
                norm_text="",
                source_path=str(r["source_path"]),
                entity_id=str(r["entity_id"]),
                score=_bm25_to_score(float(r["rank"])),
            )
            for r in rows
        ]

    # -- sync state helpers (internal, for incremental sync) -------------

    def _load_all_state(self) -> dict[str, _DocState]:
        with closing(self._connect()) as con:
            cur = con.execute(
                """SELECT source_path, entity_id, content_hash, mtime_ns, chunk_ids_json
                   FROM sparse_sync_state"""
            )
            rows = cur.fetchall()
        out: dict[str, _DocState] = {}
        for r in rows:
            raw_ids = json.loads(str(r["chunk_ids_json"]))
            if not isinstance(raw_ids, list):
                continue
            out[str(r["source_path"])] = _DocState(
                entity_id=str(r["entity_id"]),
                content_hash=str(r["content_hash"]),
                mtime_ns=int(r["mtime_ns"]),
                chunk_ids=tuple(str(x) for x in raw_ids),
            )
        return out

    def _upsert_state(
        self,
        *,
        source_path: str,
        entity_id: str,
        content_hash: str,
        mtime_ns: int,
        chunk_ids: tuple[str, ...],
    ) -> None:
        payload = json.dumps(list(chunk_ids), ensure_ascii=False)
        with closing(self._connect()) as con:
            con.execute(
                """INSERT INTO sparse_sync_state
                       (source_path, entity_id, content_hash, mtime_ns, chunk_ids_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source_path) DO UPDATE SET
                       entity_id = excluded.entity_id,
                       content_hash = excluded.content_hash,
                       mtime_ns = excluded.mtime_ns,
                       chunk_ids_json = excluded.chunk_ids_json""",
                (source_path, entity_id, content_hash, mtime_ns, payload),
            )
            con.commit()

    def _delete_state_paths(self, source_paths: list[str]) -> None:
        if not source_paths:
            return
        with closing(self._connect()) as con:
            con.executemany(
                "DELETE FROM sparse_sync_state WHERE source_path = ?",
                [(p,) for p in source_paths],
            )
            con.commit()


# ── internal helpers ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class _DocState:
    entity_id: str
    content_hash: str
    mtime_ns: int
    chunk_ids: tuple[str, ...]


def _fts_query(text: str) -> str | None:
    """将查询文本转为 FTS5 MATCH 表达式。

    1. ``_cjk_space`` 预处理（CJK 字间插空格）；
    2. 按空白分词，每个词用双引号包裹做短语匹配；
    3. 多个词之间用 AND 连接。
     """
    q = text.strip()
    if not q:
        return None
    spaced = _cjk_space(q)
    tokens = spaced.split()
    if not tokens:
        return None
    # 每个 token 做短语查询（保留词序），再用 AND 组合多词
    quoted = [f'"{t}"' for t in tokens if t.strip()]
    if not quoted:
        return None
    return " AND ".join(quoted)


def _bm25_to_score(rank: float) -> float:
    """FTS5 rank 是负值（越负越相关），转成正 score 方便融合。"""
    if rank >= 0:
        return 0.0
    return 1.0 / (1.0 - rank)


# ── default path ────────────────────────────────────────────────────────

def default_sparse_db_path(index_root: Path | None = None) -> Path:
    """默认 sparse 索引库路径（与 HSI / SVS 同置于 ``.index`` 下）。"""
    base = index_root if index_root is not None else Path(".index")
    return base / ".sparse_fts.sqlite"


# ── incremental sync ────────────────────────────────────────────────────

def sync_ksfs_sparse_incremental(
    *,
    ksfs_root: Path,
    hsi_db: Path,
    sparse_index: SqliteSparseIndex,
    sparse_db: Path,
) -> SparseSyncReport:
    """先 ``sync_ksfs_hsi``，再按 HSI 的变更检测做 **chunk 级** FTS5 增量。

    与 ``chroma_bootstrap.sync_ksfs_svs_incremental`` 平行结构。
    """
    ksfs_r = ksfs_root.resolve()
    hsi_path = hsi_db.resolve()

    hsi_report = sync_ksfs_hsi(ksfs_root=ksfs_r, hsi_db=hsi_path)
    hsi = SqliteMetadataIndex(hsi_path)

    index = sparse_index
    # 确保库 + 表已建
    index._connect().close()  # noqa: SLF001

    prev = index._load_all_state()  # noqa: SLF001

    src = FilesystemKnowledgeSource(ksfs_r)
    documents = src.iter_documents()
    keep = frozenset(document_rel_posix(d, ksfs_r) for d in documents)

    stale_paths = [p for p in prev if p not in keep]
    deleted_vec = 0
    stale_cids: list[str] = []
    for p in stale_paths:
        stale_cids.extend(prev[p].chunk_ids)
    if stale_cids:
        index.delete_ids(stale_cids)
        deleted_vec += len(stale_cids)
    if stale_paths:
        index._delete_state_paths(stale_paths)  # noqa: SLF001

    active = {p: prev[p] for p in prev if p in keep}
    doc_skipped = 0
    doc_idx = 0
    chunks_up = 0

    for doc in documents:
        rel = document_rel_posix(doc, ksfs_r)
        row = hsi.fetch_by_paths([rel]).get(rel)
        if row is None:
            continue

        _, body = split_front_matter(doc.text)
        records = build_chunk_records(rel, body or "")
        chunk_ids: list[str] = []
        texts: list[str] = []
        norm_texts: list[str] = []
        for rec in records:
            cid = compute_chunk_id(
                entity_id=row.entity_id,
                chunk_index=rec.chunk_index,
                chunk_text=rec.text,
            )
            chunk_ids.append(cid)
            texts.append(rec.text)
            norm_texts.append(rec.norm_text)

        prior = active.get(rel)
        unchanged = (
            prior is not None
            and prior.entity_id == row.entity_id
            and prior.content_hash == row.content_hash
            and prior.mtime_ns == row.mtime_ns
            and prior.chunk_ids == tuple(chunk_ids)
        )
        if unchanged:
            doc_skipped += 1
            continue

        if prior is not None and prior.chunk_ids:
            index.delete_ids(list(prior.chunk_ids))
            deleted_vec += len(prior.chunk_ids)

        if not chunk_ids:
            index._delete_state_paths([rel])  # noqa: SLF001
            doc_idx += 1
            continue

        index.upsert_chunks(
            chunk_ids=chunk_ids,
            entity_ids=[row.entity_id] * len(chunk_ids),
            source_paths=[rel] * len(chunk_ids),
            texts=texts,
            norm_texts=norm_texts,
        )
        index._upsert_state(  # noqa: SLF001
            source_path=rel,
            entity_id=row.entity_id,
            content_hash=row.content_hash,
            mtime_ns=row.mtime_ns,
            chunk_ids=tuple(chunk_ids),
        )
        doc_idx += 1
        chunks_up += len(chunk_ids)

    return SparseSyncReport(
        hsi_documents_scanned=hsi_report.documents_scanned,
        documents_indexed=doc_idx,
        documents_skipped_unchanged=doc_skipped,
        chunks_upserted=chunks_up,
        chunks_deleted_stale=deleted_vec,
    )
