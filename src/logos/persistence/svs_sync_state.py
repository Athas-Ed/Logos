"""SVS 增量同步的 SQLite 状态（每源文件对应一组 ``chunk_id``）。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS svs_doc_embedding_state (
    source_path TEXT NOT NULL PRIMARY KEY,
    entity_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    chunk_ids_json TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class SvsDocStateRow:
    source_path: str
    entity_id: str
    content_hash: str
    mtime_ns: int
    chunk_ids: tuple[str, ...]


class SvsEmbeddingStateStore:
    """记录上次成功写入 Chroma 的 ``chunk_id`` 列表，用于增量删除/跳过。"""

    __slots__ = ("_path",)

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    @property
    def db_path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._path, timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=DELETE")
        con.executescript(_SCHEMA)
        return con

    def load_all(self) -> dict[str, SvsDocStateRow]:
        with closing(self._connect()) as con:
            cur = con.execute(
                """
                SELECT source_path, entity_id, content_hash, mtime_ns, chunk_ids_json
                FROM svs_doc_embedding_state
                """
            )
            rows = cur.fetchall()
        out: dict[str, SvsDocStateRow] = {}
        for r in rows:
            raw_ids = json.loads(str(r["chunk_ids_json"]))
            if not isinstance(raw_ids, list):
                continue
            ids = tuple(str(x) for x in raw_ids)
            path = str(r["source_path"])
            out[path] = SvsDocStateRow(
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
                """
                INSERT INTO svs_doc_embedding_state
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
                "DELETE FROM svs_doc_embedding_state WHERE source_path = ?",
                [(p,) for p in source_paths],
            )
            con.commit()
