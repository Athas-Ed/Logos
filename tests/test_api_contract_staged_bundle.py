"""scripts/check_api_contract_staged_bundle.py 的轻量回归。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_api_contract_staged_bundle.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="无 git",
)
def test_bundle_fails_when_only_api_staged(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")

    rel = Path("src/logos/harness/ii_layer/api_v1.py")
    f = repo / rel
    f.parent.mkdir(parents=True)
    f.write_text("# x\n", encoding="utf-8")
    _git(repo, "add", str(rel))

    r = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "API-V0.2" in (r.stderr or "")


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="无 git",
)
def test_bundle_ok_when_api_doc_and_test_staged(tmp_path: Path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")

    paths = [
        Path("src/logos/harness/ii_layer/api_v1.py"),
        Path("original_docs/重要子系统开发文档/API-V0.2.md"),
        Path("tests/test_stream5_api.py"),
    ]
    for rel in paths:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# ok\n", encoding="utf-8")
        _git(repo, "add", str(rel))

    r = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="无 git",
)
def test_bundle_skips_when_only_doc_staged(tmp_path: Path) -> None:
    repo = tmp_path / "r3"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")

    rel = Path("original_docs/重要子系统开发文档/API-V0.2.md")
    f = repo / rel
    f.parent.mkdir(parents=True)
    f.write_text("---\n", encoding="utf-8")
    _git(repo, "add", str(rel))

    r = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
