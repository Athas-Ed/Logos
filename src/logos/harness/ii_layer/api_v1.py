"""V0.1 契约路由：``/api/v1/health`` 与 ``POST /api/v1/chat``（SSE）。"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any, Literal

_log = logging.getLogger("logos.api.v1")

from pydantic import BaseModel, Field

from logos.agent.react import ReActStreamDone, ReActStreamReasoning
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


class DeveloperUIResponse(BaseModel):
    show_dev_tools_ui: bool
    prompt_echo: bool


class PromptEchoBody(BaseModel):
    enabled: bool


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _operating_mode_suffix(mode: str) -> str:
    m = (mode or "author").strip().lower()
    if m == "screenwriter":
        return (
            "【运行模式：编剧（screenwriter）】请侧重剧本结构、场次、对白节奏与视听叙事；"
            "引用设定时务必先用 retrieve；若不确定路径，可用 list_ksfs 浏览目录，再用 read_ksfs 读原文。"
        )
    return (
        "【运行模式：作者（author）】请侧重小说叙事、人物与情节推进；"
        "需要设定依据时先 retrieve，必要时 list_ksfs + read_ksfs 核对 KSFS 文件。"
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


def _chunk_text(text: str, size: int = 512) -> Iterator[str]:
    """将长文本切成多段 SSE；默认块较大，避免把短中文用户句拆到两段导致验收/搜索断字。"""
    for i in range(0, len(text), size):
        yield text[i : i + size]


def build_v1_router() -> Any:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/api/v1", tags=["api-v1"])

    @router.get("/health")
    def health_v1() -> dict[str, str]:
        return {"status": "ok"}

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

                citation_sink: list[Citation] = []
                tools = build_v01_guarded_tool_registry(
                    ports.settings,
                    retrieval=retrieval,
                    citation_sink=citation_sink,
                )
                shell = AgentShell(
                    llm=llm,
                    tools=tools,
                    prompt_echo=ports.developer.prompt_echo,
                )

                extra = _operating_mode_suffix(body.operating_mode)
                if client_sys:
                    extra = f"{extra}\n\n【来自前端的 system 补充】\n{client_sys}"
                if ports.settings.skills_amap_weather_enabled:
                    extra += (
                        "\n\n【工具】高德实况天气已启用：用户询问气温、天气、降雨、带伞建议等时，"
                        "应调用工具 query_weather，参数 city 为中文城市/区县名或 6 位 adcode；"
                        "该查询不需要先 retrieve。"
                    )
                for item in shell.iter_run_task(
                    ut,
                    max_steps=16,
                    extra_system=extra,
                    json_mode=True,
                    history=history,
                    stream_assistant=True,
                ):
                    if isinstance(item, ReActStreamReasoning):
                        yield _sse_frame("reasoning_delta", {"text": item.text})
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
                    items = [
                        {"path": c.path, "snippet": c.snippet, "score": c.score}
                        for c in cites
                    ]
                    yield _sse_frame("citations", {"items": items})

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
        from pathlib import Path

        from logos.harness.mcp_stdio import amap_weather_mcp_command, resolve_repo_root

        cmd = amap_weather_mcp_command()
        script = Path(cmd[1])
        reg = build_v01_guarded_tool_registry(
            ports.settings,
            retrieval=retrieval,
        )
        return {
            "tools": sorted(reg.names()),
            "skills_amap_weather_enabled": ports.settings.skills_amap_weather_enabled,
            "amap_weather_script": str(script),
            "amap_weather_script_exists": script.is_file(),
            "repo_root_resolved": str(resolve_repo_root()),
            "web_api_key_configured": bool(
                (ports.settings.skills_amap_weather_web_api_key or "").strip()
            ),
        }

    return router
