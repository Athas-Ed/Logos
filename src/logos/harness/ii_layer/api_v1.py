"""V0.1 契约路由：``/api/v1/health``、``GET /api/v1/bootstrap``、``POST /api/v1/chat``（SSE）。"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any, Literal, cast

_log = logging.getLogger("logos.api.v1")

from pydantic import BaseModel, Field

from logos.agent.react import (
    ReActStreamDone,
    ReActStreamReasoning,
    ReActStreamToolTrace,
)
from logos.agent.shell import AgentShell
from logos.harness.sg_layer import build_v01_guarded_tool_registry
from logos.ports.llm import ChatMessage
from logos.ports.retrieval import Citation

from .deps import AppPortsDep, LLMDep, RetrievalDep


class ChatMessageBody(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequestBody(BaseModel):
    messages: list[ChatMessageBody]
    operating_mode: str = Field(default="author", description="operating_mode，与 SPEC 对齐")
    presentation: str | None = Field(
        default=None,
        description="展示档位 work|developer；省略则用 ui.default_presentation",
    )


class BootstrapResponse(BaseModel):
    default_presentation: Literal["work", "developer"]
    log_profile: Literal["minimal", "standard", "verbose", "audit"]
    operating_mode: str


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _effective_presentation(raw: str | None, default: str) -> Literal["work", "developer"]:
    if raw is None or not str(raw).strip():
        base = default
    else:
        base = str(raw).strip().lower()
    if base in ("developer", "dev"):
        return "developer"
    return "work"


def _operating_mode_suffix(mode: str) -> str:
    m = (mode or "author").strip().lower()
    if m == "screenwriter":
        return (
            "【运行模式：编剧（screenwriter）】请侧重剧本结构、场次、对白节奏与视听叙事；"
            "引用设定时务必先用 retrieve，再视需要用 read_lkc 查看原文。"
        )
    return (
        "【运行模式：作者（author）】请侧重小说叙事、人物与情节推进；"
        "需要设定依据时先 retrieve，再用 read_lkc 阅读细节。"
    )


def _split_request_messages(
    raw: list[ChatMessageBody],
) -> tuple[str | None, list[ChatMessage], str]:
    """拆出前端 system 补充、对话历史（不含最后一条）、当前轮用户文本。"""
    if not raw:
        return None, [], ""
    system_parts: list[str] = []
    conv: list[ChatMessage] = []
    for m in raw:
        if m.role == "system":
            if m.content.strip():
                system_parts.append(m.content.strip())
        elif m.role in ("user", "assistant"):
            conv.append(ChatMessage(role=m.role, content=m.content))
    client_extra = "\n\n".join(system_parts) if system_parts else None
    if not conv:
        return client_extra, [], ""
    last = conv[-1]
    history = conv[:-1]
    return client_extra, history, last.content


def _chunk_text(text: str, size: int = 24) -> Iterator[str]:
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
    presentation: Literal["work", "developer"], cites: list[Citation]
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
    presentation: Literal["work", "developer"], trace: ReActStreamToolTrace
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


def build_v1_router() -> Any:
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/api/v1", tags=["api-v1"])

    @router.get("/health")
    def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/bootstrap")
    def bootstrap_v1(ports: AppPortsDep) -> BootstrapResponse:
        pres = _effective_presentation(None, ports.settings.ui_default_presentation)
        prof = str(ports.settings.obs_log_profile or "standard").strip().lower()
        if prof not in ("minimal", "standard", "verbose", "audit"):
            prof = "standard"
        return BootstrapResponse(
            default_presentation=pres,
            log_profile=cast(
                Literal["minimal", "standard", "verbose", "audit"], prof
            ),
            operating_mode=ports.settings.operating_mode,
        )

    @router.post("/chat")
    def chat_v1(
        body: ChatRequestBody,
        llm: LLMDep,
        retrieval: RetrievalDep,
        ports: AppPortsDep,
    ) -> StreamingResponse:
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
                )
                shell = AgentShell(llm=llm, tools=tools)

                extra = _operating_mode_suffix(body.operating_mode)
                if client_sys:
                    extra = f"{extra}\n\n【来自前端的 system 补充】\n{client_sys}"

                result = None
                reasoning_acc: dict[str, str] = {}
                for item in shell.iter_run_task(
                    ut,
                    max_steps=16,
                    extra_system=extra,
                    json_mode=True,
                    history=history,
                    stream_assistant=True,
                ):
                    if isinstance(item, ReActStreamReasoning):
                        yield from _yield_reasoning_sse(
                            presentation, item.text, reasoning_acc
                        )
                    elif isinstance(item, ReActStreamToolTrace):
                        yield from _yield_tool_trace_sse(presentation, item)
                    elif isinstance(item, ReActStreamDone):
                        result = item.result

                if result is None:
                    yield _sse_frame(
                        "error",
                        {
                            "code": "internal",
                            "message": "Agent 未返回结束状态",
                        },
                    )
                    return

                cites = list(citation_sink)
                if not cites:
                    cites = retrieval.query(text=ut, top_k=8)
                if cites:
                    ev, payload = _citation_event(presentation, cites)
                    yield _sse_frame(ev, payload)

                for piece in _chunk_text(result.answer):
                    if piece:
                        yield _sse_frame("delta", {"text": piece})
                yield _sse_frame("done", {})
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
