"""索引增量同步状态存储：SVS 与 Sparse 共用同一 schema（物理库/表各自独立）。

- SVS 状态库：``.svs_chunk_index.sqlite`` 表 ``svs_doc_embedding_state``；
- Sparse 状态库：``.sparse_fts.sqlite`` 表 ``sparse_sync_state``（与 FTS5 同库）。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


def _schema_sql(table: str) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {table} (
    source_path TEXT NOT NULL PRIMARY KEY,
    entity_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    chunk_ids_json TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class DocSyncStateRow:
    source_path: str
    entity_id: str
    content_hash: str
    mtime_ns: int
    chunk_ids: tuple[str, ...]


class DocSyncStateStore:
    """记录上次成功写入索引的 ``chunk_id`` 列表，用于增量删除/跳过。

    表名由调用方指定（内部常量，非用户输入）；同一类按需实例化多份。
    """

    __slots__ = ("_path", "_table")

    def __init__(self, db_path: Path, *, table: str) -> None:
        self._path = db_path
        self._table = table

    @property
    def db_path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._path, timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=DELETE")
        con.executescript(_schema_sql(self._table))
        return con

    def load_all(self) -> dict[str, DocSyncStateRow]:
        with closing(self._connect()) as con:
            cur = con.execute(
                f"""
                SELECT source_path, entity_id, content_hash, mtime_ns, chunk_ids_json
                FROM {self._table}
                """
            )
            rows = cur.fetchall()
        out: dict[str, DocSyncStateRow] = {}
        for r in rows:
            raw_ids = json.loads(str(r["chunk_ids_json"]))
            if not isinstance(raw_ids, list):
                continue
            ids = tuple(str(x) for x in raw_ids)
            path = str(r["source_path"])
            out[path] = DocSyncStateRow(
                source_path=path,
                entity_id=str(r["entity_id"]),
                content_hash=str(r["content_hash"]),
                mtime_ns=int(r["mtime_ns"]),
                chunk_ids=ids,
            )
        return out

    def upsert_row(
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
                f"""
                INSERT INTO {self._table}
                    (source_path, entity_id, content_hash, mtime_ns, chunk_ids_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    content_hash = excluded.content_hash,
                    mtime_ns = excluded.mtime_ns,
                    chunk_ids_json = excluded.chunk_ids_json
                """,
                (source_path, entity_id, content_hash, mtime_ns, payload),
            )
            con.commit()

    def delete_paths(self, source_paths: list[str]) -> None:
        if not source_paths:
            return
        with closing(self._connect()) as con:
            con.executemany(
                f"DELETE FROM {self._table} WHERE source_path = ?",
                [(p,) for p in source_paths],
            )
            con.commit()
