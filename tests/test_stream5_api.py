"""Stream 5：``/api/v1`` 健康检查与 ``chat`` SSE（FastAPI + TestClient / httpx）。"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from logos.platform.ii_layer.app import create_app
from logos.platform.ii_layer.container import AppPorts
from logos.platform.ii_layer.developer import DeveloperToggles
from logos.platform.sg_layer import build_v01_guarded_tool_registry
from logos.platform.skills_registry import get_skill_manifest
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
        conversations_cache="./workspace/conversations",
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
    assert body.get("obs_show_log_root_in_gui") is False
    assert body.get("obs_logs_root") is None
    assert "conversations_cache_root" in body
    assert body["conversations_cache_root"]
    ui = body["ui"]
    assert ui["SSE_maxNum"] == 3
    assert ui["cache_warn_bytes"] == 524288000
    assert ui["max_history_full_text"] == 5
    assert ui["react_max_steps"] == 16
    assert ui["react_max_qa_steps"] == 20


def test_api_v1_bootstrap_skills(tmp_path: Path) -> None:
    """F5-08：bootstrap 含 skills[]，含 retrieve_qa（react）样例。"""
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/bootstrap")
    assert r.status_code == 200
    skills = r.json().get("skills")
    assert isinstance(skills, list)
    assert len(skills) >= 3
    by_id = {s["skill_id"]: s for s in skills}
    assert "lint_zh" in by_id
    assert by_id["lint_zh"]["paradigm"] == "dialogue"
    assert "chat_inspire" in by_id
    assert by_id["chat_inspire"]["paradigm"] == "react"
    assert "retrieve_qa" in by_id
    assert by_id["retrieve_qa"]["paradigm"] == "react"
    assert by_id["retrieve_qa"]["display_name"]
    assert "import_setting" in by_id
    assert by_id["import_setting"]["paradigm"] == "pipeline"
    assert "ui_instructions" in by_id["lint_zh"]
    assert "语病" in by_id["lint_zh"]["ui_instructions"]


def test_api_v1_bootstrap_reflects_settings(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=replace(
            ports.settings,
            ui_default_presentation="developer",
            ui_sse_max_num=5,
            ui_cache_warn_bytes=1024,
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
    assert body.get("obs_show_log_root_in_gui") is False
    assert body.get("obs_logs_root") is None
    assert body["ui"]["SSE_maxNum"] == 5
    assert body["ui"]["cache_warn_bytes"] == 1024


def test_api_v1_bootstrap_obs_o4_exposes_logs_root_when_enabled(tmp_path: Path) -> None:
    ports = _make_ports(tmp_path)
    logs = tmp_path / "logs"
    ports = AppPorts(
        settings=replace(
            ports.settings,
            obs_show_log_root_in_gui=True,
            logs_root=str(logs),
            conversations_cache="./workspace/conversations",
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
    assert body["obs_show_log_root_in_gui"] is True
    assert body["obs_logs_root"] == str(logs.resolve())


def test_api_v1_bootstrap_llm_mode_stub_without_api_key(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.get("/api/v1/bootstrap")
    assert r.status_code == 200
    assert r.json()["llm_mode"] == "stub"


def test_api_v1_chat_paradigm_override_plan(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path, developer_show_ui=True))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "skill_id": "lint_zh",
                "paradigm_override": "plan",
                "messages": [{"role": "user", "content": "试范式覆盖"}],
            },
            headers={"Accept": "text/event-stream"},
        ) as stream:
            assert stream.status_code == 200
            raw = stream.read().decode("utf-8")
    assert "event: done" in raw
    assert "not_implemented" not in raw


def test_api_v1_chat_chat_inspire_multi_turn_messages(tmp_path: Path) -> None:
    """F5-07：chat_inspire react 多轮 messages[] 可 SSE 完成。"""
    app = create_app(_make_ports(tmp_path))
    messages = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "已收到第一句"},
        {"role": "user", "content": "第二句"},
    ]
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={"skill_id": "chat_inspire", "messages": messages},
            headers={"Accept": "text/event-stream"},
        ) as stream:
            assert stream.status_code == 200
            raw = stream.read().decode("utf-8")
    assert "event: done" in raw


def test_api_v1_chat_with_skill_id_lint_zh(tmp_path: Path) -> None:
    from logos.agent.cb import REACT_JSON_MANDATE_MARKERS

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
            headers={"Accept": "text/event-stream"},
        ) as stream:
            assert stream.status_code == 200
            raw = stream.read().decode("utf-8")
    assert "event: done" in raw
    assert REACT_JSON_MANDATE_MARKERS[0] not in raw


def test_api_v1_chat_unknown_skill_id_returns_400(tmp_path: Path) -> None:
    app = create_app(_make_ports(tmp_path))
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/chat",
            json={
                "skill_id": "no_such_skill_xyz",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 400
    assert "no_such_skill_xyz" in r.text or "not found" in r.text.lower()


def test_registry_tool_names_subset_of_manifest_allowed_tools(tmp_path: Path) -> None:
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
    manifest = get_skill_manifest("lint_zh")
    reg = build_v01_guarded_tool_registry(
        settings,
        allowed_tools=frozenset(manifest.allowed_tools),
    )
    assert set(reg.names()) <= set(manifest.allowed_tools)


def test_api_v1_chat_sse_delta_and_done(tmp_path: Path) -> None:
    """缺省 skill_id → chat_inspire（react），有 ReAct reasoning 事件。"""
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
            json={
                "skill_id": "retrieve_qa",
                "messages": [{"role": "user", "content": "请引用"}],
            },
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert "event: citations_partial" in raw
    assert "demo.md" in raw


def test_retrieve_qa_react_registry_scoped_tools(tmp_path: Path) -> None:
    manifest = get_skill_manifest("retrieve_qa")
    assert manifest.paradigm == "react"
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
    reg = build_v01_guarded_tool_registry(
        settings,
        allowed_tools=frozenset(manifest.allowed_tools),
    )
    assert set(reg.names()) == {"retrieve", "read_ksfs"}


@pytest.mark.skipif(
    importlib.util.find_spec("httpx") is None,
    reason="未安装 httpx",
)
def test_api_v1_chat_via_httpx_async_asgi(tmp_path: Path) -> None:
    import asyncio

    import httpx

    from logos.platform.ii_layer.app import create_app

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
    delta_blocks = [
        b
        for b in raw.split("\n\n")
        if b.strip().startswith("event: delta")
    ]
    assert len(delta_blocks) == 1, "prompt 回显应单次 delta 下发，避免前端拼接重复"
    assert "event: citations" not in raw, "prompt 回显不应阻塞检索引用"


def test_api_v1_chat_prompt_echo_skips_slow_retrieval(tmp_path: Path) -> None:
    import time

    class _SlowRetrieval:
        def query(self, text: str, top_k: int = 8):  # noqa: ARG002
            time.sleep(5)
            return []

    class _ExplodingLLM(_StubLLM):
        def stream_completion(self, messages, *, json_mode: bool = False):
            msg = "LLM 不应在 prompt 回显模式下被调用"
            raise RuntimeError(msg)

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
            json={"messages": [{"role": "user", "content": "测"}]},
        ) as stream:
            raw = stream.read().decode("utf-8")
    assert time.perf_counter() - t0 < 2.0
    assert "【Prompt 回显模式】" in raw
