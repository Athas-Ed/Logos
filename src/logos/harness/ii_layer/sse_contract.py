"""``POST /api/v1/chat`` 的 SSE 契约常量与载荷校验。

与 ``original_docs/重要子系统开发文档/API-V0.1.md``、GUI ``sseChat.ts`` 对齐；
契约单测见 ``tests/test_sse_chat_contract.py``。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Final

# 服务端可能发出的 chat SSE 事件名（不含默认 event:message）
CHAT_SSE_EVENT_NAMES: Final[frozenset[str]] = frozenset(
    {"reasoning_delta", "citations", "delta", "done", "error"}
)

# 文档与单测共用的「最小合法」示例 JSON（object 形态，便于对照 API 表）
CHAT_SSE_MINIMAL_JSON: Final[dict[str, dict[str, Any]]] = {
    "reasoning_delta": {"text": ""},
    "delta": {"text": ""},
    "citations": {"items": [{"path": "", "snippet": "", "score": 0.0}]},
    "done": {},
    "error": {"code": "", "message": ""},
}


def iter_chat_sse_events(raw: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """解析 ``StreamingResponse`` 读出的 UTF-8 文本，产出 ``(event_name, data_obj)``。"""
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
        if not data_lines:
            continue
        merged = "\n".join(data_lines)
        payload = json.loads(merged)
        if not isinstance(payload, dict):
            msg = f"SSE data 必须为 JSON object，event={event_name!r}"
            raise TypeError(msg)
        yield event_name, payload


def validate_chat_sse_payload(event: str, payload: dict[str, Any]) -> None:
    """校验单条事件的 JSON 是否满足当前契约的最小字段与类型。"""
    if event not in CHAT_SSE_EVENT_NAMES:
        msg = f"未知或未文档化的 chat SSE 事件: {event!r}"
        raise ValueError(msg)
    if event in ("delta", "reasoning_delta"):
        if "text" not in payload:
            msg = f"事件 {event!r} 缺少必填字段 text"
            raise ValueError(msg)
        if not isinstance(payload["text"], str):
            msg = f"事件 {event!r} 的 text 须为 string"
            raise TypeError(msg)
    elif event == "citations":
        items = payload.get("items")
        if not isinstance(items, list):
            msg = "事件 citations 的 items 须为 array"
            raise TypeError(msg)
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                msg = f"citations.items[{idx}] 须为 object"
                raise TypeError(msg)
            for key in ("path", "snippet", "score"):
                if key not in it:
                    msg = f"citations.items[{idx}] 缺少字段 {key!r}"
                    raise ValueError(msg)
    elif event == "error":
        for key in ("code", "message"):
            if key not in payload:
                msg = f"事件 error 缺少必填字段 {key!r}"
                raise ValueError(msg)
            if not isinstance(payload[key], str):
                msg = f"事件 error 的 {key!r} 须为 string"
                raise TypeError(msg)
    # done: 允许任意 object（含空对象），不额外约束
