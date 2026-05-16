from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _run_promote_draft(
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(_REPO / "src")}
    return subprocess.run(
        [sys.executable, "-m", "logos.tools.promote_draft", *args],
        cwd=str(cwd or _REPO),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_promote_draft_help_readable() -> None:
    cp = _run_promote_draft("--help")
    assert cp.returncode == 0
    out = (cp.stdout + cp.stderr).lower()
    assert "dry-run" in out
    assert "apply" in out
    assert "--workspace" in cp.stdout
    assert "--target-ksfs" in cp.stdout


def test_promote_draft_dry_run_no_writes(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    drafts = ws / "setting_entry" / "batch_a"
    drafts.mkdir(parents=True)
    (drafts / "note.md").write_text("---\ntitle: t\n---\nbody\n", encoding="utf-8")
    (drafts / "README.md").write_text("# ignored\n", encoding="utf-8")

    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()

    before = list(ksfs.rglob("*"))
    cp = _run_promote_draft(
        "--workspace",
        str(ws),
        "--target-ksfs",
        str(ksfs),
        "--dry-run",
        cwd=tmp_path,
    )
    assert cp.returncode == 0
    assert "候选数: 1" in cp.stdout
    assert "note.md" in cp.stdout
    assert "mtime_ns=" in cp.stdout
    after = list(ksfs.rglob("*"))
    assert after == before


def test_promote_draft_apply_and_hsi(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "setting_entry").mkdir(parents=True)
    (ws / "setting_entry" / "x.md").write_text("# X\n\nhi\n", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    hsi = tmp_path / ".index" / ".high-speed_index"

    cp = _run_promote_draft(
        "--workspace",
        str(ws),
        "--target-ksfs",
        str(ksfs),
        "--apply",
        "--hsi-db",
        str(hsi),
        cwd=tmp_path,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    assert (ksfs / "x.md").is_file()
    from logos.persistence import SqliteMetadataIndex

    idx = SqliteMetadataIndex(hsi)
    rows = idx.search_paths(prefix="", limit=20)
    paths = {r.source_path for r in rows}
    assert "x.md" in paths


def test_promote_draft_apply_rejects_existing_target(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "setting_entry").mkdir(parents=True)
    (ws / "setting_entry" / "dup.md").write_text("# D\n\na\n", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    (ksfs / "dup.md").write_text("# old\n\n", encoding="utf-8")
    hsi = tmp_path / ".index" / ".high-speed_index"

    cp = _run_promote_draft(
        "--workspace",
        str(ws),
        "--target-ksfs",
        str(ksfs),
        "--apply",
        "--hsi-db",
        str(hsi),
        cwd=tmp_path,
    )
    assert cp.returncode == 3
    assert "拒绝" in cp.stderr or "拒绝" in cp.stdout
