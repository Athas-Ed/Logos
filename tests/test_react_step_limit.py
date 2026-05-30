"""ReAct 步数触顶：hit_step_limit 与 done SSE 载荷。"""



from __future__ import annotations



import json

from pathlib import Path



import pytest



pytest.importorskip("fastapi")



from fastapi.testclient import TestClient



from logos.agent.react import run_react_loop

from logos.agent.tool_registry import ToolRegistry

from logos.platform.ii_layer.app import create_app

from logos.platform.ii_layer.container import AppPorts

from logos.platform.ii_layer.developer import DeveloperToggles

from logos.ports import AppSettings, McpServerEntry

from logos.ports.knowledge_source import SourceDocument

from logos.ports.retrieval import Citation





class _AlwaysToolLLM:

    """每轮 JSON 只返回 retrieve，永不 final_answer。"""



    @staticmethod

    def _tool_json() -> str:

        return json.dumps(

            {

                "thought": "继续检索",

                "action": {"name": "retrieve", "arguments": {"query": "test"}},

            },

            ensure_ascii=False,

        )



    def complete(self, messages, *, json_mode: bool = False) -> str:

        if json_mode:

            return self._tool_json()

        return "收束作答：依据已有观测。"



    def stream_completion(self, messages, *, json_mode: bool = False):

        yield self._tool_json()





class _StubRetrieval:

    def query(self, *, text: str, top_k: int = 8):

        return [Citation(path="a.md", snippet="s", score=0.5)]





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





def _make_ports(tmp_path: Path, *, llm: object) -> AppPorts:

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

        react_max_steps=3,

        react_max_qa_steps=3,

    )

    return AppPorts(

        settings=settings,

        llm=llm,

        retrieval=_StubRetrieval(),

        knowledge_source=_StubKnowledgeSource(),

        metadata_index=_StubMetadataIndex(),

        semantic_store=_StubSemanticStore(),

        text_embedder=_StubEmbedder(),

        developer=DeveloperToggles(prompt_echo=False),

    )





def _parse_sse_done_payload(raw: str) -> dict | None:

    for block in raw.split("\n\n"):

        lines = [ln for ln in block.splitlines() if ln.strip()]

        if not lines:

            continue

        event_name = "message"

        data_lines: list[str] = []

        for ln in lines:

            if ln.startswith("event:"):

                event_name = ln[6:].strip()

            elif ln.startswith("data:"):

                data_lines.append(ln[5:].strip())

        if event_name == "done" and data_lines:

            return json.loads("\n".join(data_lines))

    return None





def test_coerce_natural_answer_from_json() -> None:

    from logos.agent.react import _coerce_natural_answer



    raw = '{"thought":"x","final_answer":"自然语言答复"}'

    assert _coerce_natural_answer(raw) == "自然语言答复"





def test_run_react_loop_hit_step_limit() -> None:

    reg = ToolRegistry()

    reg.register(

        "retrieve",

        description="检索",

        parameters={"type": "object", "properties": {"query": {"type": "string"}}},

        handler=lambda query: "observation",

    )

    res = run_react_loop(

        _AlwaysToolLLM(),

        reg,

        "问题",

        max_steps=3,

    )

    assert res.hit_step_limit is True

    assert res.steps == 3

    assert "本轮上限" not in res.answer

    assert res.answer.strip()





def test_chat_sse_emits_react_hit_step_limit_only(tmp_path: Path) -> None:

    app = create_app(_make_ports(tmp_path, llm=_AlwaysToolLLM()))

    with TestClient(app) as client:

        r = client.post(

            "/api/v1/chat",

            json={

                "skill_id": "retrieve_qa",

                "messages": [{"role": "user", "content": "测步数上限"}],

            },

            headers={"Accept": "text/event-stream"},

        )

    assert r.status_code == 200

    text = r.text

    assert "react_hit_step_limit" in text

    done = _parse_sse_done_payload(text)

    assert done is not None

    assert done.get("react_hit_step_limit") is True

    assert "react_can_continue" not in done

    assert "react_resume_messages" not in done

    assert "本次 ReAct 步数已达本轮上限" not in text.split("event: done")[0]

