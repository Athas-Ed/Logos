"""HSI: SQLite-backed MetadataIndex."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from logos.ports.metadata import MetadataRecord


_SCHEMA = """
CREATE TABLE IF NOT EXISTS hsi_metadata (
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL PRIMARY KEY,
    content_hash TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hsi_source_path_prefix ON hsi_metadata (source_path);
"""


class SqliteMetadataIndex:
    """Structured index at ``db_path`` (e.g. ``.index/.high-speed_index``)."""

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
        # DELETE avoids WAL sidecars; Windows temp cleanup won't hit locked -wal.
        con.execute("PRAGMA journal_mode=DELETE")
        con.executescript(_SCHEMA)
        return con

    def upsert(self, records: list[MetadataRecord]) -> None:
        if not records:
            return
        with closing(self._connect()) as con:
            con.executemany(
                """
                INSERT INTO hsi_metadata (entity_id, title, source_path, content_hash, mtime_ns)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    title = excluded.title,
                    content_hash = excluded.content_hash,
                    mtime_ns = excluded.mtime_ns
                """,
                [
                    (r.entity_id, r.title, r.source_path, r.content_hash, r.mtime_ns)
                    for r in records
                ],
            )
            con.commit()

    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        lim = max(0, limit)
        with closing(self._connect()) as con:
            if prefix:
                cur = con.execute(
                    """
                    SELECT entity_id, title, source_path, content_hash, mtime_ns
                    FROM hsi_metadata
                    WHERE source_path LIKE ?
                    ORDER BY source_path
                    LIMIT ?
                    """,
                    (prefix.replace("\\", "/") + "%", lim),
                )
            else:
                cur = con.execute(
                    """
                    SELECT entity_id, title, source_path, content_hash, mtime_ns
                    FROM hsi_metadata
                    ORDER BY source_path
                    LIMIT ?
                    """,
                    (lim,),
                )
            rows = cur.fetchall()
        return [
            MetadataRecord(
                entity_id=str(r["entity_id"]),
                title=str(r["title"]),
                source_path=str(r["source_path"]),
                content_hash=str(r["content_hash"]),
                mtime_ns=int(r["mtime_ns"]),
            )
            for r in rows
        ]

    def delete_paths(self, source_paths: list[str]) -> None:
        """Remove rows (e.g. when KSFS files disappear from scan set)."""
        if not source_paths:
            return
        with closing(self._connect()) as con:
            con.executemany(
                "DELETE FROM hsi_metadata WHERE source_path = ?",
                [(p,) for p in source_paths],
            )
            con.commit()

    def fetch_by_paths(self, source_paths: list[str]) -> dict[str, MetadataRecord]:
        """Batch read for incremental comparison."""
        if not source_paths:
            return {}
        uniq = list(dict.fromkeys(source_paths))
        placeholders = ",".join("?" * len(uniq))
        with closing(self._connect()) as con:
            cur = con.execute(
                f"""
                SELECT entity_id, title, source_path, content_hash, mtime_ns
                FROM hsi_metadata
                WHERE source_path IN ({placeholders})
                """,
                uniq,
            )
            rows = cur.fetchall()
        return {
            str(r["source_path"]): MetadataRecord(
                entity_id=str(r["entity_id"]),
                title=str(r["title"]),
                source_path=str(r["source_path"]),
                content_hash=str(r["content_hash"]),
                mtime_ns=int(r["mtime_ns"]),
            )
            for r in rows
        }

    def delete_not_in(self, keep: frozenset[str]) -> int:
        """Remove rows whose ``source_path`` is not in ``keep``; returns delete count."""
        with closing(self._connect()) as con:
            cur = con.execute("SELECT source_path FROM hsi_metadata")
            stale = [str(r[0]) for r in cur.fetchall() if str(r[0]) not in keep]
            for p in stale:
                con.execute("DELETE FROM hsi_metadata WHERE source_path = ?", (p,))
            con.commit()
        return len(stale)
