from __future__ import annotations

from pathlib import Path

from logos.persistence import SqliteMetadataIndex
from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort


def test_apply_mtime_mismatch_aborts(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "setting_entry").mkdir(parents=True)
    f = ws / "setting_entry" / "a.md"
    f.write_text("# A\n", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    hsi = tmp_path / "hsi.db"

    port = FilesystemDraftPromotionPort(hsi_db=hsi)
    items = port.list_promotion_candidates(ws / "setting_entry", ksfs)
    assert len(items) == 1
    f.write_text("# A\n\nmore\n", encoding="utf-8")
    report = port.apply_promotion(ws / "setting_entry", ksfs, items)
    assert not report.ok
    assert "mtime" in report.notes
    assert not (ksfs / "a.md").exists()


def test_apply_success_hsi_row(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "setting_entry" / "sub").mkdir(parents=True)
    (ws / "setting_entry" / "sub" / "b.md").write_text("# B\n\nbody\n", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    hsi = tmp_path / "hsi.db"

    port = FilesystemDraftPromotionPort(hsi_db=hsi)
    items = port.list_promotion_candidates(ws / "setting_entry", ksfs)
    report = port.apply_promotion(ws / "setting_entry", ksfs, items)
    assert report.ok
    assert "sub/b.md" in report.applied
    idx = SqliteMetadataIndex(hsi)
    rows = idx.search_paths(prefix="sub/", limit=10)
    assert any(r.source_path == "sub/b.md" for r in rows)
