"""A3：``POST /api/v1/chat`` SSE 分档位事件契约（与 API-V0.2、api_v1、GUI 对齐）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.platform.ii_layer.app import create_app
from logos.platform.ii_layer.container import AppPorts
from logos.platform.ii_layer.developer import DeveloperToggles
from logos.platform.ii_layer.sse_contract import (
    CHAT_SSE_EVENT_NAMES,
    CHAT_SSE_MINIMAL_JSON,
    iter_chat_sse_events,
    validate_chat_sse_payload,
)
from logos.ports import AppSettings
from logos.ports.knowledge_source import SourceDocument
from logos.ports.retrieval import Citation


class _StubLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        users = [m for m in messages if m.role == "user"]
        last_user = users[-1].content if users else ""
        if json_mode:
            return json.dumps(
                {"thought": "stub", "final_answer": "答：" + last_user},
                ensure_ascii=False,
            )
        return "答：" + last_user

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        step = 8
        for i in range(0, len(text), step):
            yield text[i : i + step]


class _StubRetrieval:
    def query(self, *, text: str, top_k: int = 8):
        return []


class _StubKnowledgeSource:
    def iter_documents(self) -> list[SourceDocument]:
        return []

    def read_document(self, relative_path: str) -> SourceDocument:
        raise FileNotFoundError(relative_path)


class _StubMetadataIndex:
    def upsert(self, records) -> None:  # noqa: ANN001
        return None

    def search_paths(self, *, prefix: str | None, limit: int):
        return []


class _StubSemanticStore:
    def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
        return None

    def delete_ids(self, ids: list[str]) -> None:
        return None

    def query(self, query_embedding: list[float], top_k: int):
        return []


class _StubEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 512 for _ in texts]


def _make_ports(tmp_path: Path) -> AppPorts:
    settings = AppSettings(
        workspace_root=str(tmp_path / "workspace"),
        example_ksfs_root=str(tmp_path / "ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / ".index"),
        logs_root=str(tmp_path / "logs"),
        conversations_cache="./workspace/conversations",
        hsi_sqlite_path=str(tmp_path / ".index" / "hsi.sqlite"),
        chroma_persist_directory=str(tmp_path / ".index" / "vec"),
        chroma_collection="t",
        embedding_provider="stub",
        embedding_model_path="stub",
    )
    return AppPorts(
        settings=settings,
        llm=_StubLLM(),
        retrieval=_StubRetrieval(),
        knowledge_source=_StubKnowledgeSource(),
        metadata_index=_StubMetadataIndex(),
        semantic_store=_StubSemanticStore(),
        text_embedder=_StubEmbedder(),
        developer=DeveloperToggles(prompt_echo=False),
    )


def test_minimal_json_examples_validate() -> None:
    for event, obj in CHAT_SSE_MINIMAL_JSON.items():
        validate_chat_sse_payload(event, obj)


def test_iter_chat_sse_events_roundtrip() -> None:
    raw = (
        'event: reasoning_summary\ndata: {"text": "a"}\n\n'
        'event: delta\ndata: {"text": "b"}\n\n'
        'event: done\ndata: {}\n\n'
    )
    events = list(iter_chat_sse_events(raw))
    assert events == [
        ("reasoning_summary", {"text": "a"}),
        ("delta", {"text": "b"}),
        ("done", {}),
    ]


def test_contract_full_stream_from_app(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "retrieve_qa",
                "messages": [{"role": "user", "content": "契约"}],
            },
            headers={"Accept": "text/event-stream"},
        ) as stream:
            raw = stream.read().decode("utf-8")
    parsed = list(iter_chat_sse_events(raw))
    assert parsed, "应至少解析出一条 SSE"
    for event, payload in parsed:
        assert event in CHAT_SSE_EVENT_NAMES
        validate_chat_sse_payload(event, payload)
    names = [e for e, _ in parsed]
    assert "reasoning_summary" in names
    assert "delta" in names
    assert names[-1] == "done"


def test_contract_empty_user_yields_error_only(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "   "}]},
        ) as stream:
            raw = stream.read().decode("utf-8")
    events = list(iter_chat_sse_events(raw))
    assert len(events) == 1
    ev, payload = events[0]
    assert ev == "error"
    assert payload.get("code") == "empty_message"
    validate_chat_sse_payload("error", payload)


def test_contract_developer_presentation_emits_reasoning_full(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "retrieve_qa",
                "messages": [{"role": "user", "content": "契约"}],
                "presentation": "developer",
            },
            headers={"Accept": "text/event-stream"},
        ) as stream:
            raw = stream.read().decode("utf-8")
    names = [e for e, _ in iter_chat_sse_events(raw)]
    assert "reasoning_full" in names
    assert "reasoning_summary" not in names
    for ev, pl in iter_chat_sse_events(raw):
        validate_chat_sse_payload(ev, pl)


def test_contract_citations_items_shape(tmp_path: Path) -> None:
    class _CiteRetrieval(_StubRetrieval):
        def query(self, *, text: str, top_k: int = 8):
            return [Citation(path="p.md", snippet="s", score=0.5)]

    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=ports.settings,
        llm=ports.llm,
        retrieval=_CiteRetrieval(),
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
                "skill_id": "retrieve_qa",
                "messages": [{"role": "user", "content": "请引用"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    cite_events = [
        pl for ev, pl in iter_chat_sse_events(raw) if ev == "citations_partial"
    ]
    assert cite_events
    validate_chat_sse_payload("citations_partial", cite_events[0])
