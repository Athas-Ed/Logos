"""Stream 2：HDL 哈希与 KSFS→HSI 同步行为单测。"""

from __future__ import annotations

from pathlib import Path

from logos.persistence import (
    IndexSync,
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
    assert r1.fm_id_writebacks == 1
    assert r1.hsi_ids_allocated == 1
    text = md.read_text(encoding="utf-8")
    assert 'id: "10001"' in text

    r2 = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r2.hsi_upserted == 0
    assert r2.hsi_skipped_unchanged == 1
    assert r2.fm_id_writebacks == 0

    md.write_text("# T\n\nbody v2\n", encoding="utf-8")
    r3 = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r3.hsi_upserted == 1
    assert r3.hsi_skipped_unchanged == 0


def test_sync_ksfs_hsi_duplicate_id_conflict_reassigns(tmp_path: Path) -> None:
    ksfs = tmp_path / "ksfs"
    hsi = tmp_path / "hsi" / "db.sqlite"
    (ksfs / "a").mkdir(parents=True)
    (ksfs / "b").mkdir(parents=True)
    (ksfs / "a" / "x.md").write_text(
        '---\nid: "10001"\ntitle: A\n---\n\nalpha\n',
        encoding="utf-8",
    )
    (ksfs / "b" / "y.md").write_text(
        '---\nid: "10001"\ntitle: B\n---\n\nbeta\n',
        encoding="utf-8",
    )
    r = sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    assert r.hsi_id_conflicts_resolved >= 1
    assert r.hsi_ids_allocated >= 1
    ids = {
        line.strip()
        for p in sorted(ksfs.rglob("*.md"))
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith('id: "')
    }
    assert ids == {'id: "10001"', 'id: "10002"'}


def test_index_sync_once_is_idempotent(tmp_path: Path) -> None:
    ksfs = tmp_path / "ksfs"
    hsi = tmp_path / "hsi" / "db.sqlite"
    (ksfs / "doc").mkdir(parents=True)
    (ksfs / "doc" / "note.md").write_text("# T\n\nonce\n", encoding="utf-8")

    sync = IndexSync(ksfs_root=ksfs, hsi_db=hsi)
    r1 = sync.sync_once()
    r2 = sync.sync_once()
    assert r1 is not None
    assert r2 is None
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
def test_compute_chunk_id_matches_spec_payload() -> None:
    from logos.persistence import compute_chunk_id

    cid = compute_chunk_id(entity_id="10001", chunk_index=0, chunk_text="alpha")
    assert cid.startswith("ck_")
    assert len(cid) == len("ck_") + 64


def test_chunk_markdown_heading_sections() -> None:
    from logos.persistence import chunk_markdown_body

    body = "# A\n\nshort\n\n## B\n\n" + ("x" * 50) + "\n"
    parts = chunk_markdown_body(body, min_chars=120)
    assert len(parts) >= 1
    assert "# A" in parts[0] or "short" in parts[0]


def test_sync_ksfs_svs_second_run_skips_upsert(tmp_path: Path) -> None:
    from logos.persistence import sync_ksfs_hsi, sync_ksfs_indexes

    ksfs = tmp_path / "ksfs"
    idx = tmp_path / ".index"
    hsi = idx / ".high-speed_index"
    state = idx / ".svs_chunk_index.sqlite"
    (ksfs / "d").mkdir(parents=True)
    (ksfs / "d" / "n.md").write_text("---\n---\n\n# T\n\nhello world\n", encoding="utf-8")

    class _E:
        def embed(self, texts: list[str]) -> list[list[float]]:  # noqa: ANN001
            return [[0.1, 0.2] for _ in texts]

    class _S:
        def __init__(self) -> None:
            self.upserts = 0

        def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
            self.upserts += 1

        def delete_ids(self, ids: list[str]) -> None:
            return None

        def query(self, query_embedding: list[float], top_k: int):  # noqa: ANN001
            return []

    store = _S()
    emb = _E()
    sync_ksfs_hsi(ksfs_root=ksfs, hsi_db=hsi)
    r1 = sync_ksfs_indexes(
        ksfs_root=ksfs,
        hsi_db=hsi,
        semantic_store=store,
        embedder=emb,
        svs_state_db=state,
    )
    assert r1.svs_chunks_upserted >= 1
    u1 = store.upserts
    r2 = sync_ksfs_indexes(
        ksfs_root=ksfs,
        hsi_db=hsi,
        semantic_store=store,
        embedder=emb,
        svs_state_db=state,
    )
    assert r2.svs_documents_skipped_unchanged >= 1
    assert r2.svs_chunks_upserted == 0
    assert store.upserts == u1
