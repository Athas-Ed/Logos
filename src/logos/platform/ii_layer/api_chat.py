"""V0.2 契约路由：SSE 对话流（``POST /api/v1/chat``）。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from logos.platform.skills_config import resolve_skill_config
from .api_v1 import (
    _effective_presentation,
    _resolve_ksfs_root,
    _resolve_workspace_root,
    _sse_frame,
)
from .deps import AppPortsDep, LLMDep, RetrievalDep

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


def _allow_paradigm_override(settings: Any) -> bool:
    if settings.developer_show_dev_tools_ui:
        return True
    return os.environ.get("LOGOS_FORCE_STUB_LLM", "").strip() == "1"


def _resolve_skill_id(raw: str | None) -> str:
    sid = (raw or "").strip()
    if sid:
        return sid
    _log.warning(
        "POST /api/v1/chat 未提供 skill_id，回退为 %s（目标态为必填 400）",
        _DEFAULT_SKILL_ID,
    )
    return _DEFAULT_SKILL_ID


def _resolve_paradigm_override(
    body: ChatRequestBody,
    skill_id: str,
    *,
    settings: Any,
    user_text: str,
) -> Any:
    from logos.agent import pr as paradigm_router

    paradigm = paradigm_router.select_paradigm(skill_id, user_text=user_text)
    raw = (body.paradigm_override or "").strip().lower()
    if not raw or not _allow_paradigm_override(settings):
        return paradigm
    if raw not in ("dialogue", "react", "plan", "pipeline"):
        _log.warning("忽略非法 paradigm_override=%r", body.paradigm_override)
        return paradigm
    return cast(Any, raw)


def _operating_mode_suffix(mode: str) -> str:
    """运行模式后缀：始终加载 author 模式。"""
    from logos.agent.cb import load_operating_mode_suffix

    _ = mode
    return load_operating_mode_suffix("author")


def _split_request_messages(
    raw: list[ChatMessageBody],
) -> tuple[str | None, list[Any], str]:
    """拆出前端 system 补充、对话历史（不含最后一条）、当前轮用户文本。"""
    from logos.ports.llm import ChatMessage

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
    ) -> StreamingResponse:
        from logos.agent.shell import AgentShell
        from logos.agent.dialogue import DialogueStreamDone, DialogueStreamText
        from logos.agent.pipeline import (
            PipelineStepEvent,
            PipelineStreamDone,
            PipelineWarningEvent,
        )
        from logos.agent.react import (
            ReActStreamDone,
            ReActStreamReasoning,
            ReActStreamToolTrace,
        )
        from logos.platform.obs.tool_chain import (
            clear_obs_log_profile_tls,
            prime_obs_log_profile_for_chat,
            reset_react_tool_steps,
        )
        from logos.platform.sg_layer import build_v01_guarded_tool_registry
        from logos.platform.sg_layer.guarded_registry import V01_SG_TOOL_WHITELIST
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
            prime_obs_log_profile_for_chat(str(ports.settings.obs_log_profile or "standard"))
            reset_react_tool_steps()
            try:
                try:
                    from logos.agent import cb as cb_mod

                    skill_cfg = resolve_skill_config(
                        skill_id, skill_manifest, ports.settings
                    )
                    react_max_steps = int(skill_cfg.get("max_steps", ports.settings.react_max_steps))
                    clip = skill_cfg.get("history_clip_max_full_turns")
                    client_sys, history, user_text = _split_request_messages(body.messages)
                    if clip is not None and history:
                        history = cb_mod.clip_turn_history(
                            history,
                            max_full_rounds=int(clip),
                        )
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
                    shell = AgentShell(
                        llm=llm,
                        tools=tools,
                        prompt_echo=ports.developer.prompt_echo,
                    )

                    extra = _operating_mode_suffix(body.operating_mode)
                    if client_sys:
                        extra = f"{extra}\n\n【来自前端的 system 补充】\n{client_sys}"
                    paradigm = _resolve_paradigm_override(
                        body,
                        skill_id,
                        settings=ports.settings,
                        user_text=ut,
                    )

                    if paradigm == "pipeline":
                        profile = skill_manifest.pipeline_profile
                        if not profile:
                            yield _sse_frame(
                                "error",
                                {
                                    "code": "invalid_skill",
                                    "message": (
                                        f"Skill {skill_id!r} 为 pipeline 但缺少 pipeline_profile"
                                    ),
                                },
                            )
                            return
                        ws_root = _resolve_workspace_root(ports.settings)
                        ksfs_root = _resolve_ksfs_root(ports.settings)
                        pipeline_finished = False
                        for item in shell.iter_paradigm_task(
                            skill_id,
                            ut,
                            max_steps=16,
                            extra_system=extra,
                            history=history,
                            task_input=body.task_input,
                            stream_assistant=True,
                            workspace_root=ws_root,
                            ksfs_root=ksfs_root,
                        ):
                            if isinstance(item, PipelineStepEvent):
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
                            elif isinstance(item, PipelineWarningEvent):
                                yield _sse_frame(
                                    "pipeline_warning",
                                    {"warnings": list(item.warnings)},
                                )
                            elif isinstance(item, PipelineStreamDone):
                                result = item.result
                                units = result.batch.get("units") or []
                                summary_lines = [
                                    f"批次 {result.batch.get('batch_id', '')}："
                                    f"共 {len(units)} 个单元，"
                                    f"已写入 {len(result.written_paths)} 个文件。",
                                ]
                                for rel in result.written_paths:
                                    summary_lines.append(f"- {rel}")
                                if result.warnings:
                                    summary_lines.append(
                                        "警告：" + "；".join(result.warnings)
                                    )
                                yield _sse_frame(
                                    "delta",
                                    {"text": "\n".join(summary_lines)},
                                )
                                yield _sse_frame(
                                    "done",
                                    {
                                        "written_paths": list(result.written_paths),
                                        "warnings": list(result.warnings),
                                        "unit_count": len(units),
                                        "batch_id": result.batch.get("batch_id"),
                                    },
                                )
                                pipeline_finished = True
                        if not pipeline_finished:
                            yield _sse_frame(
                                "error",
                                {
                                    "code": "internal",
                                    "message": "Pipeline 未正常结束",
                                },
                            )
                        return

                    if paradigm == "react":
                        mcp_tool_names = frozenset(tools.names()) - V01_SG_TOOL_WHITELIST
                        if mcp_tool_names:
                            listed = ", ".join(sorted(mcp_tool_names))
                            extra += (
                                f"\n\n【工具】以下 MCP 暴露的工具已启用：{listed}。"
                                "按用户意图在恰当时机调用；与 KSFS 无关的查询不必先 retrieve。"
                            )

                    answer_text = ""
                    reasoning_acc: dict[str, str] = {}
                    react_done: ReActStreamDone | None = None
                    for item in shell.iter_paradigm_task(
                        skill_id,
                        ut,
                        max_steps=react_max_steps,
                        extra_system=extra,
                        history=history,
                        task_input=body.task_input,
                        stream_assistant=True,
                    ):
                        if isinstance(item, DialogueStreamText):
                            answer_text += item.text
                            yield _sse_frame("delta", {"text": item.text})
                        elif isinstance(item, DialogueStreamDone):
                            answer_text = item.result.answer
                        elif isinstance(item, ReActStreamReasoning):
                            yield from _yield_reasoning_sse(
                                presentation, item.text, reasoning_acc
                            )
                        elif isinstance(item, ReActStreamToolTrace):
                            reasoning_acc.pop("reasoning_buf", None)
                            yield from _yield_tool_trace_sse(presentation, item)
                        elif isinstance(item, ReActStreamDone):
                            answer_text = item.result.answer
                            react_done = item

                    if not answer_text and not ports.developer.prompt_echo:
                        yield _sse_frame(
                            "error",
                            {
                                "code": "internal",
                                "message": "Agent 未返回结束状态",
                            },
                        )
                        return

                    if ports.developer.prompt_echo:
                        if answer_text:
                            yield _sse_frame("delta", {"text": answer_text})
                        yield _sse_frame("done", {})
                        return

                    if paradigm == "react":
                        cites = list(citation_sink)
                        if not cites:
                            cites = retrieval.query(text=ut, top_k=8)
                        if cites:
                            ev, payload = _citation_event(presentation, cites)
                            yield _sse_frame(ev, payload)
                        for piece in _chunk_text(answer_text):
                            if piece:
                                yield _sse_frame("delta", {"text": piece})
                    done_payload: dict[str, Any] = {}
                    if (
                        paradigm == "react"
                        and react_done is not None
                        and react_done.result.hit_step_limit
                    ):
                        done_payload["react_hit_step_limit"] = True
                    yield _sse_frame("done", done_payload)
                except Exception as exc:  # noqa: BLE001 — 契约要求以 error 事件结束流
                    _log.exception("POST /api/v1/chat 流处理异常")
                    msg = str(exc)
                    if isinstance(exc, OSError) and getattr(exc, "filename", None):
                        msg = f"{msg}（路径: {exc.filename!s}）"
                    yield _sse_frame(
                        "error",
                        {"code": type(exc).__name__, "message": msg},
                    )
            finally:
                reset_react_tool_steps()
                clear_obs_log_profile_tls()

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
