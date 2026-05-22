"""F6-03：import_setting manifest + POST /chat pipeline SSE + setting_entry 落盘。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.harness.ii_layer.app import create_app
from logos.harness.ii_layer.sse_contract import iter_chat_sse_events, validate_chat_sse_payload
from logos.harness.mcp_stdio import resolve_repo_root
from logos.harness.skills_registry import get_skill_manifest
from tests.test_stream5_api import _make_ports


def _minimal_import_batch_text() -> str:
    path = (
        resolve_repo_root()
        / "resources"
        / "entity_template"
        / "default_import_v0"
        / "examples"
        / "minimal_batch.json"
    )
    return path.read_text(encoding="utf-8")


class _ImportStubLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        if json_mode:
            for m in messages:
                if m.role == "system" and "结构化拆分" in m.content:
                    return _minimal_import_batch_text()
            return json.dumps(
                {"thought": "stub", "final_answer": "非导入"},
                ensure_ascii=False,
            )
        return "stub"

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        for i in range(0, len(text), 64):
            yield text[i : i + 64]


def test_import_setting_manifest() -> None:
    m = get_skill_manifest("import_setting")
    assert m.paradigm == "pipeline"
    assert m.pipeline_profile == "default_import_v0"
    assert m.persistence_tier == "p0"
    assert "粘贴" in m.ui_instructions


def test_import_setting_chat_pipeline_sse(tmp_path: Path) -> None:
    ports = replace(_make_ports(tmp_path), llm=_ImportStubLLM())
    app = create_app(ports)
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "import_setting",
                "messages": [{"role": "user", "content": "林动，青阳镇少年。"}],
                "task_input": {"text": "林动，青阳镇少年。"},
            },
        ) as stream:
            raw = stream.read().decode("utf-8")

    assert "not_implemented" not in raw
    assert "event: reasoning_summary" not in raw
    events = list(iter_chat_sse_events(raw))
    names = [e for e, _ in events]
    assert "pipeline_step" in names
    assert "delta" in names
    assert names[-1] == "done"
    for event, payload in events:
        validate_chat_sse_payload(event, payload)

    done_payload = next(p for e, p in events if e == "done")
    assert done_payload.get("unit_count") == 1
    written = done_payload.get("written_paths") or []
    assert any("setting_entry/characters/lin-dong.md" in str(p) for p in written)

    out = tmp_path / "workspace" / "setting_entry" / "characters" / "lin-dong.md"
    assert out.is_file()
    assert "林动" in out.read_text(encoding="utf-8")
