"""FTS5 实现的 SparseIndex：检索与 chunk 级写入。

增量同步统一走 ``chroma_bootstrap.sync_ksfs_indexes``（Candidate 2 合并管线），
本模块不再持有同步状态（见 ``svs_sync_state.DocSyncStateStore``）。
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

from logos.ports.sparse import SparseIndex, SparseQueryHit


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


# ── SQLite-backed SparseIndex ───────────────────────────────────────────

class SqliteSparseIndex:
    """FTS5 全文索引实现（同步状态由 ``DocSyncStateStore`` 同库管理）。"""

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


# ── internal helpers ────────────────────────────────────────────────────

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
