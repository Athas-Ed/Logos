"""Stream 5：``/api/v1`` 健康检查与 ``chat`` SSE（FastAPI + TestClient / httpx）。"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.harness.ii_layer.app import create_app
from logos.harness.ii_layer.container import AppPorts
from logos.harness.ii_layer.developer import DeveloperToggles
from logos.ports import AppSettings, McpServerEntry
from logos.ports.knowledge_source import SourceDocument
from logos.ports.retrieval import Citation


class _StubLLM:
    def complete(self, messages, *, json_mode: bool = False) -> str:
        users = [m for m in messages if m.role == "user"]
        last_user = users[-1].content if users else ""
        if json_mode:
            return json.dumps(
                {"thought": "stub", "final_answer": "答复：" + last_user},
                ensure_ascii=False,
            )
        return "答复：" + last_user

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        step = 8
        for i in range(0, len(text), step):
            yield text[i : i + step]


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


def _make_ports(
    tmp_path: Path,
    *,
    developer_show_ui: bool = False,
    developer_prompt_echo: bool = False,
    mcp_servers: tuple[McpServerEntry, ...] = (),
) -> AppPorts:
    settings = AppSettings(
        workspace_root=str(tmp_path / "workspace"),
        example_ksfs_root=str(tmp_path / "ksfs"),
        ksfs_root=str(tmp_path / "ksfs"),
        index_root=str(tmp_path / ".index"),
        logs_root=str(tmp_path / "logs"),
        hsi_sqlite_path=str(tmp_path / ".index" / "hsi.sqlite"),
        chroma_persist_directory=str(tmp_path / ".index" / "vec"),
        chroma_collection="t",
        embedding_provider="stub",
        embedding_model_path="stub",
        developer_show_dev_tools_ui=developer_show_ui,
        developer_prompt_echo=developer_prompt_echo,
        mcp_servers=mcp_servers,
    )
    return AppPorts(
        settings=settings,
        llm=_StubLLM(),
        retrieval=_StubRetrieval(),
        knowledge_source=_StubKnowledgeSource(),
        metadata_index=_StubMetadataIndex(),
        semantic_store=_StubSemanticStore(),
        text_embedder=_StubEmbedder(),
        developer=DeveloperToggles(prompt_echo=developer_prompt_echo),
    )


def test_api_v1_health(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_api_v1_bootstrap(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/bootstrap")
    assert r.status_code == 200
    body = r.json()
    assert body["default_presentation"] == "work"
    assert body["log_profile"] == "standard"
    assert "operating_mode" in body


def test_api_v1_bootstrap_reflects_settings(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=replace(
            ports.settings,
            ui_default_presentation="developer",
            obs_log_profile="verbose",
            operating_mode="screenwriter",
        ),
        llm=ports.llm,
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=ports.developer,
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.get("/api/v1/bootstrap")
    assert r.status_code == 200
    body = r.json()
    assert body["default_presentation"] == "developer"
    assert body["log_profile"] == "verbose"
    assert body["operating_mode"] == "screenwriter"


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
    assert "event: reasoning_summary" in raw
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
    assert "event: citations_partial" in raw
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


def test_api_v1_developer_ui(tmp_path: Path) -> None:
    app = create_app(
        _make_ports(tmp_path, developer_show_ui=True, developer_prompt_echo=True)
    )
    with TestClient(app) as client:
        r = client.get("/api/v1/developer/ui")
    assert r.status_code == 200
    assert r.json() == {"show_dev_tools_ui": True, "prompt_echo": True}


def test_api_v1_developer_agent_tools_forbidden(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/developer/agent-tools")
    assert r.status_code == 403


def test_api_v1_developer_agent_tools_includes_mcp(tmp_path: Path) -> None:
    mcp = (
        McpServerEntry(
            id="amap_weather",
            enabled=True,
            entrypoint="skills/amap-weather-mcp/server.py",
            strip_http_proxy=True,
            env=frozenset(),
        ),
    )
    app = create_app(
        _make_ports(
            tmp_path,
            developer_show_ui=True,
            mcp_servers=mcp,
        )
    )
    with TestClient(app) as client:
        r = client.get("/api/v1/developer/agent-tools")
    assert r.status_code == 200
    data = r.json()
    assert "query_weather" in data["tools"]
    assert any(
        x.get("id") == "amap_weather" and x.get("enabled") is True
        for x in data["mcp_servers"]
    )


def test_api_v1_developer_put_prompt_echo_forbidden(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.put("/api/v1/developer/prompt-echo", json={"enabled": True})
    assert r.status_code == 403


def test_api_v1_developer_put_prompt_echo_ok(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path, developer_show_ui=True))
    with TestClient(app) as client:
        r = client.put("/api/v1/developer/prompt-echo", json={"enabled": True})
        assert r.status_code == 200
        assert r.json() == {"prompt_echo": True}
        r2 = client.get("/api/v1/developer/ui")
        assert r2.json()["prompt_echo"] is True


def test_api_v1_chat_prompt_echo_no_llm(tmp_path: Path) -> None:
    class _ExplodingLLM(_StubLLM):
        def stream_completion(self, messages, *, json_mode: bool = False):
            msg = "LLM 不应在 prompt 回显模式下被调用"
            raise RuntimeError(msg)

    ports = _make_ports(tmp_path, developer_prompt_echo=True)
    ports = AppPorts(
        settings=ports.settings,
        llm=_ExplodingLLM(),
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
            json={"messages": [{"role": "user", "content": "你好"}]},
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "【Prompt 回显模式】" in raw
    assert "role=" in raw and "user" in raw
    assert "你好" in raw
    assert "event: done" in raw
