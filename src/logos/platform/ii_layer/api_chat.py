"""V0.2 契约路由：SSE 对话流（``POST /api/v1/chat``）。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from .api_v1 import (
    _effective_presentation,
    _sse_frame,
)
from .deps import AppPortsDep, LLMDep, ResolvedPathsDep, RetrievalDep

_log = logging.getLogger("logos.api.chat")


class ChatMessageBody(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


_DEFAULT_SKILL_ID = "chat_inspire"


class ChatRequestBody(BaseModel):
    messages: list[ChatMessageBody]
    skill_id: str | None = Field(
        default=None,
        description="产品 Skill 标识；省略时回退 chat_inspire（见 API-V0.2 §3.1）",
    )
    task_input: dict[str, Any] | None = Field(
        default=None,
        description="任务向导第二步结构化输入；结构依 manifest input_schema",
    )
    paradigm_override: str | None = Field(
        default=None,
        description=(
            "开发者试验：强制 PR 范式 dialogue|react|plan|pipeline；"
            "仅 developer.show_dev_tools_ui 或 LOGOS_FORCE_STUB_LLM=1 时生效"
        ),
    )
    operating_mode: str = Field(default="author", description="operating_mode，与 SPEC 对齐")
    presentation: str | None = Field(
        default=None,
        description="展示档位 work|developer；省略则用 ui.default_presentation",
    )


# ── 辅助函数 ──


def _resolve_skill_id(raw: str | None) -> str:
    sid = (raw or "").strip()
    if sid:
        return sid
    _log.warning(
        "POST /api/v1/chat 未提供 skill_id，回退为 %s（目标态为必填 400）",
        _DEFAULT_SKILL_ID,
    )
    return _DEFAULT_SKILL_ID


def _split_request_messages(
    raw: list[ChatMessageBody],
) -> tuple[str | None, list[Any], str]:
    """拆出前端 system 补充、对话历史（不含最后一条）、当前轮用户文本。"""
    from logos.ports.llm import ChatMessage as _ChatMessage

    if not raw:
        return None, [], ""
    system_parts: list[str] = []
    conv: list[_ChatMessage] = []
    for m in raw:
        if m.role == "system":
            if m.content.strip():
                system_parts.append(m.content.strip())
        elif m.role in ("user", "assistant"):
            conv.append(_ChatMessage(role=m.role, content=m.content))
    client_extra = "\n\n".join(system_parts) if system_parts else None
    if not conv:
        return client_extra, [], ""
    last = conv[-1]
    history = conv[:-1]
    return client_extra, history, last.content


def _chunk_text(text: str, size: int = 512) -> Iterator[str]:
    """将长文本切成多段 SSE；默认块较大，避免把短中文用户句拆到两段导致验收/搜索断字。"""
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _yield_reasoning_sse(
    presentation: Literal["work", "developer"],
    piece: str,
    acc_holder: dict[str, str],
) -> Iterator[str]:
    buf = acc_holder.setdefault("reasoning_buf", "") + piece
    acc_holder["reasoning_buf"] = buf
    if presentation == "developer":
        yield _sse_frame("reasoning_full", {"text": piece})
        return
    max_preview = 120
    preview = buf if len(buf) <= max_preview else buf[: max_preview - 1] + "…"
    yield _sse_frame("reasoning_summary", {"text": preview})


def _citation_event(
    presentation: Literal["work", "developer"], cites: list[Any]
) -> tuple[str, dict[str, Any]]:
    items_full = [
        {"path": c.path, "snippet": c.snippet, "score": c.score} for c in cites
    ]
    if presentation == "work":
        partial: list[dict[str, Any]] = []
        for c in cites[:3]:
            sn = c.snippet
            if len(sn) > 160:
                sn = sn[:157] + "…"
            partial.append({"path": c.path, "snippet": sn, "score": c.score})
        return "citations_partial", {"items": partial}
    return "citations_full", {"items": items_full}


def _yield_tool_trace_sse(
    presentation: Literal["work", "developer"], trace: Any
) -> Iterator[str]:
    if presentation == "work":
        status = "error" if trace.error else "ok"
        detail = (trace.error or trace.observation or "")[:240]
        yield _sse_frame(
            "tool_trace_summary",
            {"tool": trace.tool_name, "status": status, "detail": detail},
        )
        return
    try:
        arguments = json.loads(trace.arguments_json) if trace.arguments_json else {}
    except json.JSONDecodeError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {"_raw": trace.arguments_json}
    yield _sse_frame(
        "tool_trace_full",
        {
            "tool": trace.tool_name,
            "arguments": arguments,
            "result": trace.observation,
            "error": trace.error,
        },
    )


# ── Router ──


def build_chat_router() -> Any:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse

    router = APIRouter()

    @router.post("/chat")
    def chat_v1(
        body: ChatRequestBody,
        llm: LLMDep,
        retrieval: RetrievalDep,
        ports: AppPortsDep,
        paths: ResolvedPathsDep,
    ) -> StreamingResponse:
        from logos.agent.cb import load_operating_mode_suffix
        from logos.agent.task import (
            TaskCitations,
            TaskDone,
            TaskPipelineStep,
            TaskPipelineWarning,
            TaskReasoning,
            TaskSession,
            TaskText,
            TaskToolTrace,
        )
        from logos.platform.sg_layer import build_v01_guarded_tool_registry
        from logos.platform.skills_registry import (
            SkillManifestNotFoundError,
            get_skill_manifest,
        )
        from logos.ports.retrieval import Citation

        skill_id = _resolve_skill_id(body.skill_id)
        try:
            skill_manifest = get_skill_manifest(skill_id)
        except SkillManifestNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        def event_stream() -> Iterator[str]:
            try:
                client_sys, history, user_text = _split_request_messages(body.messages)
                ut = user_text.strip()
                if not ut:
                    yield _sse_frame(
                        "error",
                        {"code": "empty_message", "message": "缺少有效用户消息"},
                    )
                    return

                presentation = _effective_presentation(
                    body.presentation, ports.settings.ui_default_presentation
                )

                citation_sink: list[Citation] = []
                tools = build_v01_guarded_tool_registry(
                    ports.settings,
                    retrieval=retrieval,
                    citation_sink=citation_sink,
                    allowed_tools=frozenset(skill_manifest.allowed_tools),
                )
                session = TaskSession(
                    llm=llm,
                    tools=tools,
                    settings=ports.settings,
                    retrieval=retrieval,
                    citation_sink=citation_sink,
                    workspace_root=paths.workspace_root,
                    ksfs_root=paths.ksfs_root,
                    prompt_echo=ports.developer.prompt_echo,
                )

                extra = load_operating_mode_suffix(body.operating_mode)
                if client_sys:
                    extra = f"{extra}\n\n【来自前端的 system 补充】\n{client_sys}"
                reasoning_acc: dict[str, str] = {}
                done_seen = False
                for item in session.iter_task(
                    skill_id,
                    ut,
                    task_input=body.task_input,
                    history=history,
                    extra_system=extra,
                    paradigm_override=body.paradigm_override,
                ):
                    if isinstance(item, TaskText):
                        yield _sse_frame("delta", {"text": item.text})
                    elif isinstance(item, TaskReasoning):
                        yield from _yield_reasoning_sse(
                            presentation, item.text, reasoning_acc
                        )
                    elif isinstance(item, TaskToolTrace):
                        reasoning_acc.pop("reasoning_buf", None)
                        yield from _yield_tool_trace_sse(presentation, item)
                    elif isinstance(item, TaskCitations):
                        ev, payload = _citation_event(presentation, list(item.items))
                        yield _sse_frame(ev, payload)
                    elif isinstance(item, TaskPipelineStep):
                        yield _sse_frame(
                            "pipeline_step",
                            {
                                "step_id": item.step_id,
                                "status": item.status,
                                "summary": item.summary,
                            },
                        )
                        if item.status == "error":
                            yield _sse_frame(
                                "error",
                                {
                                    "code": "pipeline_step_failed",
                                    "message": item.summary,
                                },
                            )
                            return
                    elif isinstance(item, TaskPipelineWarning):
                        yield _sse_frame(
                            "pipeline_warning",
                            {"warnings": list(item.warnings)},
                        )
                    elif isinstance(item, TaskDone):
                        done_seen = True
                        if item.kind == "pipeline":
                            summary_lines = [
                                f"批次 {item.batch_id or ''}："
                                f"共 {item.unit_count} 个单元，"
                                f"已写入 {len(item.written_paths)} 个文件。",
                            ]
                            for rel in item.written_paths:
                                summary_lines.append(f"- {rel}")
                            if item.warnings:
                                summary_lines.append(
                                    "警告：" + "；".join(item.warnings)
                                )
                            yield _sse_frame(
                                "delta",
                                {"text": "\n".join(summary_lines)},
                            )
                            yield _sse_frame(
                                "done",
                                {
                                    "written_paths": list(item.written_paths),
                                    "warnings": list(item.warnings),
                                    "unit_count": item.unit_count,
                                    "batch_id": item.batch_id,
                                },
                            )
                            return
                        if item.chunked:
                            for piece in _chunk_text(item.answer):
                                if piece:
                                    yield _sse_frame("delta", {"text": piece})
                        done_payload: dict[str, Any] = {}
                        if item.kind == "react" and item.hit_step_limit:
                            done_payload["react_hit_step_limit"] = True
                        yield _sse_frame("done", done_payload)
                        return

                if not done_seen and not ports.developer.prompt_echo:
                    yield _sse_frame(
                        "error",
                        {
                            "code": "internal",
                            "message": "Agent 未返回结束状态",
                        },
                    )
            except Exception as exc:  # noqa: BLE001 — 契约要求以 error 事件结束流
                _log.exception("POST /api/v1/chat 流处理异常")
                msg = str(exc)
                if isinstance(exc, OSError) and getattr(exc, "filename", None):
                    msg = f"{msg}（路径: {exc.filename!s}）"
                yield _sse_frame(
                    "error",
                    {"code": type(exc).__name__, "message": msg},
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
