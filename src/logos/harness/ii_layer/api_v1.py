"""V0.2 契约路由（路径前缀 ``/api/v1``）：health、bootstrap、chat（SSE）、developer 端点。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, cast

from logos.agent.paradigm_types import Paradigm
from logos.ports.settings import AppSettings

_log = logging.getLogger("logos.api.v1")

from pydantic import BaseModel, Field

from logos.agent import pr as paradigm_router
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
from logos.agent.shell import AgentShell
from logos.harness.mcp_stdio import resolve_repo_root
from logos.harness.obs.tool_chain import (
    clear_obs_log_profile_tls,
    prime_obs_log_profile_for_chat,
    reset_react_tool_steps,
)
from logos.harness.skills_registry import (
    SkillManifestNotFoundError,
    get_skill_manifest,
)
from logos.harness.sg_layer import build_v01_guarded_tool_registry
from logos.harness.sg_layer.guarded_registry import V01_SG_TOOL_WHITELIST
from logos.ports.llm import ChatMessage
from logos.ports.retrieval import Citation

from .deps import AppPortsDep, LLMDep, RetrievalDep


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


def _allow_paradigm_override(settings: AppSettings) -> bool:
    if settings.developer_show_dev_tools_ui:
        return True
    return os.environ.get("LOGOS_FORCE_STUB_LLM", "").strip() == "1"


def _resolve_llm_mode(settings: AppSettings) -> Literal["stub", "remote"]:
    if os.environ.get("LOGOS_FORCE_STUB_LLM", "").strip() == "1":
        return "stub"
    if not (settings.llm_api_key or "").strip():
        return "stub"
    return "remote"


def _resolve_paradigm_override(
    body: "ChatRequestBody",
    skill_id: str,
    *,
    settings: AppSettings,
    user_text: str,
) -> Paradigm:
    paradigm = paradigm_router.select_paradigm(skill_id, user_text=user_text)
    raw = (body.paradigm_override or "").strip().lower()
    if not raw or not _allow_paradigm_override(settings):
        return paradigm
    if raw not in ("dialogue", "react", "plan", "pipeline"):
        _log.warning("忽略非法 paradigm_override=%r", body.paradigm_override)
        return paradigm
    return cast(Paradigm, raw)


def _resolve_skill_id(raw: str | None) -> str:
    sid = (raw or "").strip()
    if sid:
        return sid
    _log.warning(
        "POST /api/v1/chat 未提供 skill_id，回退为 %s（目标态为必填 400）",
        _DEFAULT_SKILL_ID,
    )
    return _DEFAULT_SKILL_ID


class DeveloperUIResponse(BaseModel):
    show_dev_tools_ui: bool
    prompt_echo: bool


class PromptEchoBody(BaseModel):
    enabled: bool


class BootstrapUiPayload(BaseModel):
    SSE_maxNum: int
    cache_warn_bytes: int


class BootstrapSkillPayload(BaseModel):
    """产品 Skill 摘要，供 GUI 技能面板（F5-08）。"""

    skill_id: str
    display_name: str
    description: str
    ui_instructions: str = ""
    persistence_tier: Literal["p0", "p1", "p2"]
    paradigm: Literal["dialogue", "react", "plan", "pipeline"]


class SettingEntryPromoteBody(BaseModel):
    """将 ``workspace/setting_entry/`` 下草稿晋升至 KSFS（F6-08）。"""

    draft_relpaths: list[str] | None = Field(
        default=None,
        description="相对 setting_entry 根的路径；省略则晋升全部候选",
    )


class SettingEntryPromoteResponse(BaseModel):
    ok: bool
    applied: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    notes: str = ""


class BootstrapResponse(BaseModel):
    default_presentation: Literal["work", "developer"]
    log_profile: Literal["minimal", "standard", "verbose", "audit"]
    operating_mode: str
    llm_mode: Literal["stub", "remote"]
    obs_show_log_root_in_gui: bool = False
    obs_logs_root: str | None = None
    #: 解析后的档 B 会话目录绝对路径（``paths.CONVERSATIONS_CACHE``）
    conversations_cache_root: str
    ui: BootstrapUiPayload
    skills: list[BootstrapSkillPayload] = Field(default_factory=list)


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    # 紧凑 JSON：减少 SSE 带宽与 ``json.dumps`` 少量开销（S13 小步优化）
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event}\ndata: {body}\n\n"


def _effective_presentation(raw: str | None, default: str) -> Literal["work", "developer"]:
    if raw is None or not str(raw).strip():
        base = default
    else:
        base = str(raw).strip().lower()
    if base in ("developer", "dev"):
        return "developer"
    return "work"


def _operating_mode_suffix(mode: str) -> str:
    from logos.agent.cb import load_operating_mode_suffix

    return load_operating_mode_suffix(mode)


def _resolve_workspace_root(settings: AppSettings) -> Path:
    p = Path(settings.workspace_root)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


def _resolve_ksfs_root(settings: AppSettings) -> Path:
    p = Path(settings.ksfs_root)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


def _resolve_hsi_db(settings: AppSettings) -> Path:
    p = Path(settings.hsi_sqlite_path)
    if not p.is_absolute():
        p = resolve_repo_root() / p
    return p.resolve()


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
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/api/v1", tags=["api-v1"])

    @router.get("/health")
    def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/bootstrap")
    def bootstrap_v1(ports: AppPortsDep) -> BootstrapResponse:
        from logos.harness.config.paths_resolve import resolve_conversations_cache_abs
        from logos.harness.mcp_stdio import resolve_repo_root
        from logos.harness.skills_registry import list_bootstrap_skill_summaries

        pres = _effective_presentation(None, ports.settings.ui_default_presentation)
        prof = str(ports.settings.obs_log_profile or "standard").strip().lower()
        if prof not in ("minimal", "standard", "verbose", "audit"):
            prof = "standard"
        show_root = bool(ports.settings.obs_show_log_root_in_gui)
        logs_abs: str | None = None
        if show_root:
            logs_abs = str(Path(ports.settings.logs_root).expanduser().resolve())
        skill_payloads = [
            BootstrapSkillPayload(
                skill_id=s.skill_id,
                display_name=s.display_name,
                description=s.description,
                ui_instructions=s.ui_instructions,
                persistence_tier=s.persistence_tier,
                paradigm=s.paradigm,
            )
            for s in list_bootstrap_skill_summaries()
        ]
        repo = resolve_repo_root()
        conv_cache_abs = str(
            resolve_conversations_cache_abs(
                repo, ports.settings.conversations_cache
            )
        )
        return BootstrapResponse(
            default_presentation=pres,
            log_profile=cast(
                Literal["minimal", "standard", "verbose", "audit"], prof
            ),
            operating_mode=ports.settings.operating_mode,
            llm_mode=_resolve_llm_mode(ports.settings),
            obs_show_log_root_in_gui=show_root,
            obs_logs_root=logs_abs,
            conversations_cache_root=conv_cache_abs,
            ui=BootstrapUiPayload(
                SSE_maxNum=ports.settings.ui_sse_max_num,
                cache_warn_bytes=ports.settings.ui_cache_warn_bytes,
            ),
            skills=skill_payloads,
        )

    @router.post("/chat")
    def chat_v1(
        body: ChatRequestBody,
        llm: LLMDep,
        retrieval: RetrievalDep,
        ports: AppPortsDep,
    ) -> StreamingResponse:
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
                    for item in shell.iter_paradigm_task(
                        skill_id,
                        ut,
                        max_steps=16,
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
                            yield from _yield_tool_trace_sse(presentation, item)
                        elif isinstance(item, ReActStreamDone):
                            answer_text = item.result.answer

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

    @router.post("/setting-entry/promote")
    def setting_entry_promote_v1(
        body: SettingEntryPromoteBody,
        ports: AppPortsDep,
    ) -> SettingEntryPromoteResponse:
        """人审后将 setting_entry 草稿复制至 KSFS 并触发 HSI 同步。"""
        from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort

        ws_root = _resolve_workspace_root(ports.settings)
        ksfs_root = _resolve_ksfs_root(ports.settings)
        drafts_root = ws_root / "setting_entry"
        hsi_db = _resolve_hsi_db(ports.settings)
        port = FilesystemDraftPromotionPort(hsi_db=hsi_db)
        candidates = port.list_promotion_candidates(drafts_root, ksfs_root)
        if body.draft_relpaths is not None:
            allowed = {p.strip().replace("\\", "/") for p in body.draft_relpaths if p.strip()}
            candidates = [c for c in candidates if c.draft_relpath in allowed]
        if not candidates:
            return SettingEntryPromoteResponse(
                ok=True,
                applied=[],
                skipped=[],
                notes="无匹配的可晋升草稿",
            )
        report = port.apply_promotion(drafts_root, ksfs_root, candidates)
        return SettingEntryPromoteResponse(
            ok=report.ok,
            applied=list(report.applied),
            skipped=list(report.skipped),
            notes=report.notes,
        )

    @router.get("/developer/ui")
    def developer_ui(ports: AppPortsDep) -> DeveloperUIResponse:
        return DeveloperUIResponse(
            show_dev_tools_ui=ports.settings.developer_show_dev_tools_ui,
            prompt_echo=ports.developer.prompt_echo,
        )

    @router.put("/developer/prompt-echo")
    def developer_set_prompt_echo(
        body: PromptEchoBody,
        ports: AppPortsDep,
    ) -> dict[str, bool]:
        if not ports.settings.developer_show_dev_tools_ui:
            raise HTTPException(
                status_code=403,
                detail="配置 developer.show_dev_tools_ui 为 false，禁止运行时切换。",
            )
        ports.developer.prompt_echo = body.enabled
        return {"prompt_echo": body.enabled}

    @router.get("/developer/agent-tools")
    def developer_agent_tools(
        ports: AppPortsDep,
        retrieval: RetrievalDep,
    ) -> dict[str, Any]:
        """列出当前会注入对话的 Agent 工具名（含 MCP）；仅开发 UI 开启时可用。"""
        if not ports.settings.developer_show_dev_tools_ui:
            raise HTTPException(
                status_code=403,
                detail="配置 developer.show_dev_tools_ui 为 false，禁止查看。",
            )
        from logos.harness.mcp_stdio import resolve_repo_root

        repo = resolve_repo_root()
        reg = build_v01_guarded_tool_registry(
            ports.settings,
            retrieval=retrieval,
        )
        mcp_status: list[dict[str, Any]] = []
        for e in ports.settings.mcp_servers:
            script = (repo / e.entrypoint).resolve()
            mcp_status.append(
                {
                    "id": e.id,
                    "enabled": e.enabled,
                    "entrypoint": e.entrypoint,
                    "entrypoint_exists": script.is_file(),
                    "strip_http_proxy": e.strip_http_proxy,
                }
            )
        return {
            "tools": sorted(reg.names()),
            "mcp_servers": mcp_status,
            "repo_root_resolved": str(repo),
        }

    return router
