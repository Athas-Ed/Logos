"""PR-3：dialogue 执行器与 API 无检索阻塞。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.agent.cb import REACT_JSON_MANDATE_MARKERS
from logos.harness.ii_layer.app import create_app
from logos.harness.ii_layer.container import AppPorts
from logos.harness.ii_layer.developer import DeveloperToggles
from tests.test_stream5_api import _StubLLM, _make_ports


class _SlowRetrieval:
    def query(self, text: str, top_k: int = 8):  # noqa: ARG002
        time.sleep(5)
        return []


class _ExplodingLLM(_StubLLM):
    def stream_completion(self, messages, *, json_mode: bool = False):
        msg = "LLM 不应在 prompt 回显模式下被调用"
        raise RuntimeError(msg)


def test_dialogue_prompt_echo_skips_slow_retrieval(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path, developer_prompt_echo=True)
    ports = AppPorts(
        settings=ports.settings,
        llm=_ExplodingLLM(),
        retrieval=_SlowRetrieval(),
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=ports.developer,
    )
    app = create_app(ports)
    t0 = time.perf_counter()
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "lint_zh",
                "messages": [{"role": "user", "content": "测"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert time.perf_counter() - t0 < 2.0
    assert "【Prompt 回显模式】" in raw
    assert REACT_JSON_MANDATE_MARKERS[0] not in raw


def test_api_v1_lint_zh_dialogue_no_react_json_header(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "lint_zh",
                "task_input": {"text": "他跑的很快。"},
                "messages": [{"role": "user", "content": "他跑的很快。"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "event: done" in raw
    assert "event: delta" in raw
    assert REACT_JSON_MANDATE_MARKERS[0] not in raw
    assert "event: reasoning_summary" not in raw


def test_pipeline_paradigm_not_implemented(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from logos.agent import pr as pr_mod

    monkeypatch.setattr(pr_mod, "select_paradigm", lambda _sid, **_: "pipeline")
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "lint_zh",
                "messages": [{"role": "user", "content": "x"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "not_implemented" in raw
    assert "event: reasoning_summary" not in raw
