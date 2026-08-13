"""TaskSession 直测：统一 TaskEvent 流、merge 修复、prompt_echo 旁路、TLS、citations。

架构评审 Candidate 1 阶段 1：executor 之上的统一入口 seam 测试面。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from logos.agent.task import (
    TaskCitations,
    TaskDone,
    TaskReasoning,
    TaskSession,
    TaskText,
    TaskToolTrace,
    merge_task_input_into_user,
)
from logos.agent.tool_registry import ToolRegistry
from logos.ports import AppSettings
from logos.ports.retrieval import Citation


class _EchoLLM:
    """最后一条 user 文本回显为 final_answer（react）/ 直接回显（dialogue）。"""

    @staticmethod
    def _last_user_text(messages) -> str:
        for m in reversed(messages):
            if m.role == "user":
                return m.content
        return ""

    def complete(self, messages, *, json_mode: bool = False) -> str:
        last = self._last_user_text(messages)
        if json_mode:
            return json.dumps({"thought": "stub", "final_answer": "答：" + last}, ensure_ascii=False)
        return "答：" + last

    def stream_completion(self, messages, *, json_mode: bool = False):
        yield self.complete(messages, json_mode=json_mode)


class _ExplodingLLM:
    """prompt_echo 旁路下不应被调用。"""

    def complete(self, messages, *, json_mode: bool = False) -> str:
        raise RuntimeError("LLM 不应在 prompt_echo 旁路中被调用")

    def stream_completion(self, messages, *, json_mode: bool = False):
        raise RuntimeError("LLM 不应在 prompt_echo 旁路中被调用")


class _CiteRetrieval:
    def query(self, *, text: str, top_k: int = 8):
        return [Citation(path="demo.md", snippet="片段", score=0.88)]


class _EmptyRetrieval:
    def query(self, *, text: str, top_k: int = 8):
        return []


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
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


def _empty_registry() -> ToolRegistry:
    return ToolRegistry()


# ── merge 修复（Q6） ──


def test_merge_task_input_keeps_text_and_fields_together() -> None:
    merged = merge_task_input_into_user(
        "用户正文",
        {"text": "结构化的任务输入", "style": "古风", "count": 3},
    )
    assert "用户正文" in merged
    assert "结构化的任务输入" in merged
    assert "style：古风" in merged
    assert "count：3" in merged


def test_merge_task_input_text_matches_base_no_dup() -> None:
    merged = merge_task_input_into_user(
        "正文", {"text": "正文", "style": "古风"}
    )
    assert merged.count("正文") == 1
    assert "style：古风" in merged


def test_merge_task_input_empty_task_input_unchanged() -> None:
    assert merge_task_input_into_user("  正文  ", None) == "正文"


# ── TaskSession：dialogue 统一事件流 ──


def test_task_session_dialogue_emits_text_and_done(tmp_path: Path) -> None:
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_empty_registry(),
        settings=_settings(tmp_path),
    )
    events = list(session.iter_task("lint_zh", "他跑的很快。"))
    texts = [e for e in events if isinstance(e, TaskText)]
    done = [e for e in events if isinstance(e, TaskDone)]
    assert texts
    assert len(done) == 1
    assert done[0].kind == "dialogue"
    assert done[0].answer


# ── TaskSession：react 统一事件流 + citations fallback（Q8） ──


def _react_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        "retrieve",
        description="检索",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=lambda query: json.dumps([], ensure_ascii=False),
    )
    return reg


def test_task_session_react_unified_events(tmp_path: Path) -> None:
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_react_registry(),
        settings=_settings(tmp_path),
        retrieval=_EmptyRetrieval(),
    )
    events = list(session.iter_task("retrieve_qa", "查设定"))
    kinds = {type(e).__name__ for e in events}
    assert "TaskReasoning" in kinds
    assert "TaskDone" in kinds
    done = [e for e in events if isinstance(e, TaskDone)][0]
    assert done.kind == "react"
    assert done.chunked is True
    assert "查设定" in done.answer


def test_task_session_citations_fallback_when_sink_empty(tmp_path: Path) -> None:
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_react_registry(),
        settings=_settings(tmp_path),
        retrieval=_CiteRetrieval(),
        citation_sink=[],
    )
    events = list(session.iter_task("retrieve_qa", "查设定"))
    cites = [e for e in events if isinstance(e, TaskCitations)]
    assert cites
    assert cites[0].items[0].path == "demo.md"


def test_task_session_citations_from_sink_skips_fallback(tmp_path: Path) -> None:
    sink = [Citation(path="from_sink.md", snippet="s", score=0.5)]
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_react_registry(),
        settings=_settings(tmp_path),
        retrieval=_CiteRetrieval(),
        citation_sink=sink,
    )
    events = list(session.iter_task("retrieve_qa", "查设定"))
    cites = [e for e in events if isinstance(e, TaskCitations)]
    assert cites
    assert cites[0].items[0].path == "from_sink.md"


# ── TaskSession：prompt_echo 旁路（Q4） ──


def test_task_session_prompt_echo_never_calls_llm(tmp_path: Path) -> None:
    session = TaskSession(
        llm=_ExplodingLLM(),
        tools=_empty_registry(),
        settings=_settings(tmp_path),
        prompt_echo=True,
    )
    events = list(session.iter_task("lint_zh", "测"))
    texts = [e for e in events if isinstance(e, TaskText)]
    done = [e for e in events if isinstance(e, TaskDone)]
    assert texts
    assert "【Prompt 回显模式】" in texts[0].text
    assert done and done[0].kind == "dialogue"


def test_task_session_prompt_echo_react(tmp_path: Path) -> None:
    session = TaskSession(
        llm=_ExplodingLLM(),
        tools=_react_registry(),
        settings=_settings(tmp_path),
        prompt_echo=True,
    )
    events = list(session.iter_task("retrieve_qa", "测"))
    texts = [e for e in events if isinstance(e, TaskText)]
    assert texts and "【Prompt 回显模式】" in texts[0].text


# ── TaskSession：TLS 生命周期（Q5） ──


def test_task_session_clears_tls_after_run(tmp_path: Path) -> None:
    from logos.platform.obs.tool_chain import (
        current_obs_profile,
        next_react_tool_step_index,
        reset_react_tool_steps,
    )

    reset_react_tool_steps()
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_empty_registry(),
        settings=_settings(tmp_path),
    )
    list(session.iter_task("lint_zh", "测"))
    # TLS 已清理：步号重新从 1 开始，profile 回退默认
    reset_react_tool_steps()
    assert next_react_tool_step_index() == 1
    assert current_obs_profile() == "standard"


# ── TaskSession：paradigm_override 校验（仅 developer 模式） ──


def test_task_session_override_requires_dev_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from logos.agent import pr as pr_mod

    settings = _settings(tmp_path)
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_empty_registry(),
        settings=settings,
    )
    monkeypatch.setattr(pr_mod, "select_paradigm", lambda _sid, **_: "react")
    events = list(session.iter_task("lint_zh", "测", paradigm_override="dialogue"))
    done = [e for e in events if isinstance(e, TaskDone)][0]
    # 未开 developer UI：override 被忽略 → 仍走 react
    assert done.kind == "react"


def test_task_session_override_with_dev_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace

    from logos.agent import pr as pr_mod

    settings = replace(_settings(tmp_path), developer_show_dev_tools_ui=True)
    session = TaskSession(
        llm=_EchoLLM(),
        tools=_empty_registry(),
        settings=settings,
    )
    monkeypatch.setattr(pr_mod, "select_paradigm", lambda _sid, **_: "react")
    events = list(session.iter_task("lint_zh", "测", paradigm_override="dialogue"))
    done = [e for e in events if isinstance(e, TaskDone)][0]
    assert done.kind == "dialogue"
