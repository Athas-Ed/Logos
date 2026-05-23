"""Stream 7：路径沙箱、GuardedToolRegistry、示例 stdio 子进程起停。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from logos.platform.sg_layer import (
    GuardedToolRegistry,
    PathSandboxViolationError,
    build_v01_guarded_tool_registry,
    resolve_path_under_root,
    write_draft_under_workspace,
)
from logos.ports import AppSettings


def test_resolve_rejects_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    with pytest.raises(PathSandboxViolationError):
        resolve_path_under_root(root, str(tmp_path / "other" / "a.txt"))


def test_resolve_rejects_parent_segments(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    with pytest.raises(PathSandboxViolationError):
        resolve_path_under_root(root, "../escape.txt")


def test_write_draft_success(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    msg = write_draft_under_workspace(root, "drafts/x.md", "hello")
    assert "已写入" in msg
    assert (root / "drafts" / "x.md").read_text(encoding="utf-8") == "hello"


def test_write_draft_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    msg = write_draft_under_workspace(root, "../secret.txt", "hack")
    assert msg.startswith("error:")


def test_guarded_registry_rejects_unlisted_registration() -> None:
    reg = GuardedToolRegistry()
    with pytest.raises(ValueError, match="白名单"):
        reg.register(
            "rm_rf",
            description="nope",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "x",
        )


def test_guarded_registry_blocks_execute_for_non_whitelist() -> None:
    reg = GuardedToolRegistry(allowed_names=frozenset({"write_draft"}))
    reg.register(
        "write_draft",
        description="d",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        handler=lambda path, content: f"{path}:{content}",
    )
    assert "拒绝" in reg.execute("retrieve", {})


def test_build_v01_guarded_tool_registry_writes_under_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    settings = AppSettings(
        workspace_root=str(ws),
        example_ksfs_root=str(tmp_path / "ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / "idx"),
        logs_root=str(tmp_path / "logs"),
        conversations_cache="./workspace/conversations",
        hsi_sqlite_path=str(tmp_path / "idx" / "hsi"),
        chroma_persist_directory=str(tmp_path / "idx" / "chroma"),
        chroma_collection="c",
        embedding_provider="bge_small_zh",
        embedding_model_path="models/x",
    )
    reg = build_v01_guarded_tool_registry(settings)
    ok = reg.execute(
        "write_draft",
        {"path": "a/b.md", "content": "body"},
    )
    assert "已写入" in ok
    assert (ws / "a" / "b.md").read_text(encoding="utf-8") == "body"


def test_list_ksfs_tool_lists_subdirectory(tmp_path: Path) -> None:
    ks = tmp_path / "ksfs"
    (ks / "Test").mkdir(parents=True)
    (ks / "Test" / "山巅城堡.md").write_text("# x\n", encoding="utf-8")
    settings = AppSettings(
        workspace_root=str(tmp_path / "workspace"),
        example_ksfs_root=str(tmp_path / "ex"),
        ksfs_root=str(ks),
        index_root=str(tmp_path / "idx"),
        logs_root=str(tmp_path / "logs"),
        conversations_cache="./workspace/conversations",
        hsi_sqlite_path=str(tmp_path / "idx" / "hsi"),
        chroma_persist_directory=str(tmp_path / "idx" / "chroma"),
        chroma_collection="c",
        embedding_provider="bge_small_zh",
        embedding_model_path="models/x",
    )
    reg = build_v01_guarded_tool_registry(settings)
    raw = reg.execute("list_ksfs", {"path": "Test"})
    assert "山巅城堡.md" in raw
    assert "entries" in raw


def test_stdio_echo_worker_exits_cleanly() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "example-stdio-mcp"
        / "echo_worker.py"
    )
    assert script.is_file()
    proc = subprocess.Popen(  # noqa: S603 — 固定解释器与仓库内脚本
        [sys.executable, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    proc.stdin.close()
    out, err = proc.communicate(timeout=10)
    assert proc.returncode == 0
    assert out == ""
    assert err == ""
