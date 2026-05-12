"""Stream 2：HDL 哈希与 KSFS→HSI 同步行为单测。"""

from __future__ import annotations

from pathlib import Path

from logos.persistence import (
    SqliteMetadataIndex,
    content_hash_hex,
    normalize_text_for_storage,
    sync_ksfs_hsi,
)
from logos.ports.metadata import MetadataRecord


def test_normalize_text_crlf() -> None:
    assert normalize_text_for_storage("a\r\nb\rc\n") == "a\nb\nc\n"


def test_content_hash_changes_when_text_changes() -> None:
    h1 = content_hash_hex("alpha")
    h2 = content_hash_hex("beta")
    assert h1 != h2
    assert content_hash_hex("alpha") == h1


def test_sync_ksfs_hsi_first_and_second_run(tmp_path: Path) -> None:
    ksfs = tmp_path / "ksfs"
    hsi = tmp_path / "hsi" / "db.sqlite"
    (ksfs / "doc").mkdir(parents=True)
    md = ksfs / "doc" / "note.md"
    md.write_text("# T\n\nbody v1\n", encoding="utf-8")

    r1 = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r1.documents_scanned == 1
    assert r1.hsi_upserted == 1
    assert r1.hsi_skipped_unchanged == 0

    r2 = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r2.hsi_upserted == 0
    assert r2.hsi_skipped_unchanged == 1

    md.write_text("# T\n\nbody v2\n", encoding="utf-8")
    r3 = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r3.hsi_upserted == 1
    assert r3.hsi_skipped_unchanged == 0


def test_hsi_search_paths_by_prefix(tmp_path: Path) -> None:
    db = tmp_path / "hsi.sqlite"
    idx = SqliteMetadataIndex(db)
    idx.upsert(
        [
            MetadataRecord(
                entity_id="e1",
                title="标题",
                source_path="entities/x/profile.md",
                content_hash="0" * 64,
                mtime_ns=1,
            )
        ]
    )
    rows = idx.search_paths(prefix="entities/x", limit=10)
    assert len(rows) == 1
    assert rows[0].source_path == "entities/x/profile.md"
