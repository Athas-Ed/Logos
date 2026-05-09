"""V0.1 契约路由：``/api/v1/health`` 与 ``POST /api/v1/chat``（SSE）。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from logos.ports.llm import ChatMessage

from .deps import LLMDep, RetrievalDep


class ChatMessageBody(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequestBody(BaseModel):
    messages: list[ChatMessageBody]
    operating_mode: str = Field(default="author", description="operating_mode，与 SPEC 对齐")


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def build_v1_router() -> Any:
    from fastapi import APIRouter
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
    ) -> StreamingResponse:
        def event_stream() -> Iterator[str]:
            try:
                user_msgs = [m for m in body.messages if m.role == "user"]
                last_user = user_msgs[-1].content.strip() if user_msgs else ""
                if last_user:
                    cites = retrieval.query(text=last_user, top_k=8)
                    if cites:
                        items = [
                            {"path": c.path, "snippet": c.snippet, "score": c.score}
                            for c in cites
                        ]
                        yield _sse_frame("citations", {"items": items})
                port_messages = [
                    ChatMessage(role=m.role, content=m.content) for m in body.messages
                ]
                assistant = llm.complete(port_messages, json_mode=False)
                step = 48
                for i in range(0, len(assistant), step):
                    yield _sse_frame("delta", {"text": assistant[i : i + step]})
                yield _sse_frame("done", {})
            except Exception as exc:  # noqa: BLE001 — 契约要求以 error 事件结束流
                yield _sse_frame(
                    "error",
                    {"code": type(exc).__name__, "message": str(exc)},
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return router
