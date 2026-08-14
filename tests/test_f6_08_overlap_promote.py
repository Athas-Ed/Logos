"""F6-08：重叠检测 warnings[] + setting_entry 晋升 KSFS。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.agent.pipeline import PipelineRunner, PipelineWarningEvent
from logos.platform.ii_layer.app import create_app
from logos.persistence import SqliteMetadataIndex
from logos.persistence.setting_import import scan_import_overlap, validate_import_batch
from logos.persistence.setting_import.profile import load_entity_template_profile
from tests.test_pipeline_f6_02 import _load_batch
from tests.test_stream5_api import _make_ports


def test_overlap_scan_warns_existing_draft_and_ksfs(tmp_path: Path) -> None:
    profile = load_entity_template_profile("your_profile_v1")
    batch = _load_batch("minimal_batch.json")
    validate_import_batch(batch, profile.schema_path)

    ws = tmp_path / "workspace"
    ws.mkdir()
    drafts = ws / "pending_review" / "setting_entry" / "人物"
    drafts.mkdir(parents=True)
    (drafts / "lin-dong.md").write_text("# existing draft\n", encoding="utf-8")

    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    (ksfs / "人物").mkdir(parents=True)
    (ksfs / "人物" / "lin-dong.md").write_text("# existing ksfs\n", encoding="utf-8")

    warnings = scan_import_overlap(
        batch,
        profile=profile,
        workspace_root=ws,
        ksfs_root=ksfs,
    )
    assert len(warnings) >= 2
    assert any("草稿路径已存在" in w for w in warnings)
    assert any("KSFS 目标路径已存在" in w for w in warnings)


def test_pipeline_overlap_sse_warning(tmp_path: Path) -> None:
    profile = load_entity_template_profile("your_profile_v1")
    batch = _load_batch("minimal_batch.json")
    ws = tmp_path / "workspace"
    (ws / "pending_review" / "setting_entry" / "人物").mkdir(parents=True)
    (ws / "pending_review" / "setting_entry" / "人物" / "lin-dong.md").write_text("x", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()

    runner = PipelineRunner(
        profile_id="your_profile_v1",
        workspace_root=ws,
        ksfs_root=ksfs,
        llm=None,
    )
    warnings_events: list[tuple[str, ...]] = []
    for item in runner.iter_run(
        "ignored",
        batch_json=batch,
        skip_step_types=frozenset({"llm_json"}),
    ):
        if isinstance(item, PipelineWarningEvent):
            warnings_events.append(item.warnings)
    assert warnings_events
    assert any("草稿路径已存在" in w for w in warnings_events[0])


def test_setting_entry_promote_api(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    drafts = ws / "pending_review" / "setting_entry"
    drafts.mkdir(parents=True)
    (drafts / "promote-me.md").write_text("# Draft\n\nbody\n", encoding="utf-8")
    ksfs = tmp_path / "ksfs"
    ksfs.mkdir()
    hsi = tmp_path / ".index" / "hsi.sqlite"

    ports = replace(
        _make_ports(tmp_path),
        settings=replace(
            _make_ports(tmp_path).settings,
            workspace_root=str(ws),
            ksfs_root=str(ksfs),
            hsi_sqlite_path=str(hsi),
        ),
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/setting-entry/promote",
            json={"draft_relpaths": ["promote-me.md"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "promote-me.md" in body["applied"]
    assert (ksfs / "promote-me.md").is_file()

    idx = SqliteMetadataIndex(hsi)
    rows = idx.search_paths(prefix="", limit=20)
    paths = {row.source_path for row in rows}
    assert "promote-me.md" in paths
