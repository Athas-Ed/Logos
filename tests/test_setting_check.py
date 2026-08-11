"""setting_check：核心服务 + API 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.agent.setting_check import run_setting_check
from logos.platform.ii_layer.app import create_app
from logos.platform.ii_layer.container import AppPorts
from logos.platform.ii_layer.developer import DeveloperToggles
from logos.ports import AppSettings
from logos.ports.retrieval import Citation
from tests.test_stream5_api import _make_ports


class _CheckStubLLM:
    """json_mode 下返回预置冲突 JSON；非 json_mode 返回纯文本。"""

    def complete(self, messages, *, json_mode: bool = False) -> str:
        _ = messages
        if json_mode:
            return json.dumps(
                {
                    "conflicts": [
                        {
                            "item_index": 0,
                            "level": "error",
                            "ksfs_entry_path": "人物/张三.md",
                            "description": "设定中张三是人类医生，大纲描述其为机器人，直接矛盾",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return "未发现冲突"

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        yield text


class _CheckStubLLMNoConflict:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        _ = messages
        if json_mode:
            return json.dumps({"conflicts": []}, ensure_ascii=False)
        return "未发现冲突"

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        yield text


class _CheckStubLLMGarbage:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        _ = messages
        if json_mode:
            return "这不是合法 JSON {{{"
        return "未发现冲突"

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        yield text


class _CheckStubRetrieval:
    def query(self, *, text: str, top_k: int = 8):
        _ = text
        _ = top_k
        return [Citation(path="人物/张三.md", snippet="张三：人类医生", score=0.9)]


def test_run_setting_check_returns_conflicts() -> None:
    result = run_setting_check(
        [{"index": 0, "content": "设计主角张三的出场：深夜实验室偶遇故障 AI 机器人"}],
        retrieval=_CheckStubRetrieval(),
        llm=_CheckStubLLM(),
    )
    assert result.ok is False
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.item_index == 0
    assert c.level == "error"
    assert c.ksfs_entry_path == "人物/张三.md"
    assert "矛盾" in c.description


def test_run_setting_check_no_conflict() -> None:
    result = run_setting_check(
        [{"index": 0, "content": "张三在医院值班"}],
        retrieval=_CheckStubRetrieval(),
        llm=_CheckStubLLMNoConflict(),
    )
    assert result.ok is True
    assert result.conflicts == []


def test_run_setting_check_garbage_output_falls_back_empty() -> None:
    result = run_setting_check(
        [{"index": 0, "content": "任意内容"}],
        retrieval=_CheckStubRetrieval(),
        llm=_CheckStubLLMGarbage(),
    )
    assert result.ok is True
    assert result.conflicts == []


def test_run_setting_check_invalid_item_index_filtered() -> None:
    """LLM 返回的 item_index 不在请求项内时被过滤。"""

    class _LLM:
        def complete(self, messages, *, json_mode: bool = False) -> str:
            _ = messages
            if json_mode:
                return json.dumps(
                    {
                        "conflicts": [
                            {
                                "item_index": 99,
                                "level": "error",
                                "ksfs_entry_path": "x.md",
                                "description": "不在请求项内",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            return ""

        def stream_completion(self, messages, *, json_mode: bool = False):
            yield self.complete(messages, json_mode=json_mode)

    result = run_setting_check(
        [{"index": 0, "content": "a"}],
        retrieval=_CheckStubRetrieval(),
        llm=_LLM(),
    )
    assert result.conflicts == []


def test_setting_check_manifest() -> None:
    from logos.platform.skills_registry import get_skill_manifest
    from logos.agent.pr import select_paradigm

    m = get_skill_manifest("setting_check")
    assert m.paradigm == "dialogue"
    assert m.turn_policy == "single"
    assert m.panel_visible is True
    assert select_paradigm("setting_check") == "dialogue"


def test_api_v1_setting_check(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=ports.settings,
        llm=_CheckStubLLM(),
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=DeveloperToggles(prompt_echo=False),
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/setting-check",
            json={
                "items": [{"index": 0, "content": "张三在实验室遇到故障 AI"}],
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["conflicts"] == [
        {
            "item_index": 0,
            "level": "error",
            "ksfs_entry_path": "人物/张三.md",
            "description": "设定中张三是人类医生，大纲描述其为机器人，直接矛盾",
        }
    ]


def test_api_v1_setting_check_empty_items(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=ports.settings,
        llm=_CheckStubLLM(),
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=DeveloperToggles(prompt_echo=False),
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.post("/api/v1/setting-check", json={"items": []})
    assert r.status_code == 200
    assert r.json()["conflicts"] == []


def test_api_v1_setting_check_no_conflict(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=ports.settings,
        llm=_CheckStubLLMNoConflict(),
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=DeveloperToggles(prompt_echo=False),
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/setting-check",
            json={"items": [{"index": 0, "content": "张三在医院值班"}]},
        )
    assert r.status_code == 200
    assert r.json()["conflicts"] == []
