"""scripts/check_api_contract_commit_msg.py 的轻量回归。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_api_contract_commit_msg.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="无 git",
)
def test_commit_msg_fails_when_api_staged_without_contract_line(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")

    rel = Path("src/logos/harness/ii_layer/api_v1.py")
    f = repo / rel
    f.parent.mkdir(parents=True)
    f.write_text("# x\n", encoding="utf-8")
    _git(repo, "add", str(rel))

    msg = repo / "COMMIT_EDITMSG"
    msg.write_text("chore: touch api\n", encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_SCRIPT), str(msg)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "契约" in (r.stderr or "")


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="无 git",
)
def test_commit_msg_ok_when_contract_line_present(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")

    rel = Path("src/logos/harness/ii_layer/api_v1.py")
    f = repo / rel
    f.parent.mkdir(parents=True)
    f.write_text("# y\n", encoding="utf-8")
    _git(repo, "add", str(rel))

    msg = repo / "COMMIT_EDITMSG"
    msg.write_text("chore: touch api\n\n契约：无变更\n", encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_SCRIPT), str(msg)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
