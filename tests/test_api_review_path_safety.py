"""Candidate 3 回归：review 端点路径沙箱（/drafts/* 与 /outlines/save 拒绝逃逸）。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from dataclasses import replace

from fastapi.testclient import TestClient

from logos.platform.ii_layer.app import create_app

from tests.test_stream5_api import _make_ports


class _FilesJsonLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:  # noqa: ARG002
        import json

        return json.dumps({"files": [{"path": "../e.md", "content": "x"}]}, ensure_ascii=False)

    def stream_completion(self, messages, *, json_mode: bool = False):
        yield ""


def _drafts(ws: Path) -> Path:
    drafts = ws / "pending_review" / "setting_entry"
    drafts.mkdir(parents=True, exist_ok=True)
    return drafts


def test_write_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/drafts/write",
            json={"path": "../escape.md", "content": "x", "scope": "setting_entry"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "error" in body["result"]
    assert not (ws / "escape.md").exists()
    assert not (ws / "pending_review" / "escape.md").exists()


def test_write_rejects_absolute_path(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    outside = tmp_path / "outside.md"
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/drafts/write",
            json={"path": str(outside), "content": "x", "scope": "setting_entry"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert not outside.exists()


def test_read_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    (ws / "secret.md").write_text("s", encoding="utf-8")
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/drafts/read",
            params={"path": "../secret.md", "scope": "setting_entry"},
        )
    assert r.status_code == 400


def test_rewrite_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    ports = replace(_make_ports(tmp_path), llm=_FilesJsonLLM())
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/drafts/rewrite",
            json={
                "files": [{"path": "../e.md", "content": "x"}],
                "scope": "setting_entry",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "../e.md" in body["failed"]
    assert not (ws / "e.md").exists()


def test_delete_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    sentinel = ws / "sentinel.md"
    sentinel.write_text("keep", encoding="utf-8")
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/drafts/delete",
            json={"paths": ["../sentinel.md"], "scope": "setting_entry"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["deleted"] == []
    assert sentinel.exists()


def test_promote_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/drafts/promote",
            json={"paths": ["../escape.md"], "scope": "setting_entry"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "../escape.md" in body["failed"]
    assert not (ksfs / "escape.md").exists()


def test_scope_escape_rejected_on_list_and_write(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _drafts(ws)
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r_list = client.get("/api/v1/drafts", params={"scope": "../../"})
        r_write = client.post(
            "/api/v1/drafts/write",
            json={"path": "a.md", "content": "x", "scope": "../../"},
        )
    assert r_list.status_code == 400
    assert r_write.status_code == 400


def test_outline_save_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/outlines/save",
            json={"filename": "../evil.md", "content": "x"},
        )
    assert r.status_code == 400
    assert not (ws / "evil.md").exists()


def test_valid_write_read_delete_roundtrip(tmp_path: Path) -> None:
    drafts = _drafts(tmp_path / "workspace")
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        rw = client.post(
            "/api/v1/drafts/write",
            json={"path": "a/b.md", "content": "body", "scope": "setting_entry"},
        )
        assert rw.json()["ok"] is True
        assert (drafts / "a" / "b.md").read_text(encoding="utf-8") == "body"
        rr = client.get(
            "/api/v1/drafts/read",
            params={"path": "a/b.md", "scope": "setting_entry"},
        )
        assert rr.json()["content"] == "body"
        rd = client.post(
            "/api/v1/drafts/delete",
            json={"paths": ["a/b.md"], "scope": "setting_entry"},
        )
        assert rd.json()["ok"] is True
    assert not (drafts / "a" / "b.md").exists()