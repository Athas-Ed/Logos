"""F5-09 / PR-5：Plan Phase A 与 demo skill outline_plan。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logos.agent import cb, plan
from logos.agent.dialogue import DialogueStreamDone
from logos.agent.cb import REACT_JSON_MANDATE_MARKERS
from logos.agent.pr import select_paradigm
from logos.harness.skills_registry import get_skill_manifest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.harness.ii_layer.app import create_app
from tests.test_stream5_api import _make_ports

_PLAN_JSON = json.dumps(
    {
        "title": "火星殖民地科幻短篇",
        "steps": ["确定核心冲突与视角", "列出三幕结构", "撰写场景提纲"],
    },
    ensure_ascii=False,
)


class _PlanStubLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        _ = messages
        if json_mode:
            return _PLAN_JSON
        return _PLAN_JSON

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        yield text


def test_outline_plan_manifest() -> None:
    m = get_skill_manifest("outline_plan")
    assert m.paradigm == "plan"
    assert m.turn_policy == "single"
    assert select_paradigm("outline_plan") == "plan"


def test_build_plan_system_message_no_react_mandate() -> None:
    system = cb.build_plan_system_message("outline_plan")
    assert "steps" in system.lower() or "步骤" in system
    for marker in REACT_JSON_MANDATE_MARKERS:
        assert marker not in system


def test_run_plan_phase_a_returns_steps_json() -> None:
    done = None
    for item in plan.iter_plan_phase_a(
        _PlanStubLLM(),
        "outline_plan",
        "写一篇火星殖民地科幻短篇",
        task_input={"text": "火星殖民地科幻短篇"},
        stream_assistant=False,
    ):
        if isinstance(item, DialogueStreamDone):
            done = item
    assert done is not None
    raw = done.result.answer
    data = json.loads(raw)
    assert isinstance(data.get("steps"), list)
    assert len(data["steps"]) >= 2


def test_api_v1_outline_plan_sse(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    from logos.harness.ii_layer.container import AppPorts

    ports = AppPorts(
        settings=ports.settings,
        llm=_PlanStubLLM(),
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=ports.developer,
    )
    app = create_app(ports)
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "outline_plan",
                "task_input": {"text": "火星殖民地科幻短篇"},
                "messages": [{"role": "user", "content": "请列写作大纲"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "event: done" in raw
    assert "event: delta" in raw
    assert "not_implemented" not in raw
    assert REACT_JSON_MANDATE_MARKERS[0] not in raw
    assert "steps" in raw
