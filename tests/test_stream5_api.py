"""Stream 5：``/api/v1`` 健康检查与 ``chat`` SSE（FastAPI + TestClient / httpx）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.harness.ii_layer.app import create_app
from logos.harness.ii_layer.container import AppPorts
from logos.ports import AppSettings
from logos.ports.knowledge_source import SourceDocument
from logos.ports.retrieval import Citation


class _StubLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        return "答复：" + messages[-1].content


class _StubRetrieval:
    def query(self, *, text: str, top_k: int = 8):
        if "引用" in text:
            return [Citation(path="demo.md", snippet="片段", score=0.88)]
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
        index_root=str(tmp_path / ".index"),
        logs_root=str(tmp_path / "logs"),
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
    )


def test_api_v1_health(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_api_v1_chat_sse_delta_and_done(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "你好"}]},
            headers={"Accept": "text/event-stream"},
        ) as stream:
            assert stream.status_code == 200
            raw = stream.read().decode("utf-8")
    assert "event: delta" in raw
    assert "data:" in raw
    assert "event: done" in raw
    assert "答复：你好" in raw


def test_api_v1_chat_sse_citations_when_requested(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "请引用"}]},
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "event: citations" in raw
    assert "demo.md" in raw


@pytest.mark.skipif(
    importlib.util.find_spec("httpx") is None,
    reason="未安装 httpx",
)
def test_api_v1_chat_via_httpx_async_asgi(tmp_path: Path) -> None:
    import asyncio

    import httpx

    from logos.harness.ii_layer.app import create_app

    app = create_app(_make_ports(tmp_path))

    async def _run() -> str:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                "/api/v1/chat",
                json={"messages": [{"role": "user", "content": "httpx"}]},
            ) as r:
                assert r.status_code == 200
                return (await r.aread()).decode("utf-8")

    data = asyncio.run(_run())
    assert "event: done" in data
