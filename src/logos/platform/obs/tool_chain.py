"""ReAct 工具调用链结构化日志（Obs O2～O5）。

``消息`` 字段为单行 JSON，内含冻结键名（英文，便于 grep / 契约测）：
``event``、``step_index``、``tool_name``、``elapsed_ms``、``status``、
``param_digest``、``error_class``。

落盘路由：记录器 ``logos.agent.tool_chain`` → ``maint/agent.log``（见
``path_handlers.MaintSubsystemFileHandler``）。

**线程局部**：``obs.log_profile`` 与会话步号放在 :class:`threading.local` 上，
以便与 Starlette ``iterate_in_threadpool`` 下的同步生成器兼容（避免
``ContextVar`` 跨线程 ``reset`` 失败）。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any, Mapping

# --- 冻结字段（Obs O2）：仅增不改名；改名须同步 Obs 文档 + 契约测 ---
TOOL_CHAIN_EVENT_V1 = "logos_tool_chain_v1"
FIELD_EVENT = "event"
FIELD_STEP_INDEX = "step_index"
FIELD_TOOL_NAME = "tool_name"
FIELD_ELAPSED_MS = "elapsed_ms"
FIELD_STATUS = "status"
FIELD_PARAM_DIGEST = "param_digest"
FIELD_ERROR_CLASS = "error_class"

_tls = threading.local()

_SENSITIVE_KEY = re.compile(
    r"(api_?key|password|token|secret|authorization|credential|bearer|amap_web_key)$",
    re.IGNORECASE,
)


def reset_react_tool_steps() -> None:
    """新会话开始时将步号归零（由 HTTP 层调用）。"""

    _tls.react_tool_step = 0


def next_react_tool_step_index() -> int:
    """返回下一工具步序号（从 1 递增）。"""

    c = int(getattr(_tls, "react_tool_step", 0)) + 1
    _tls.react_tool_step = c
    return c


def current_obs_profile() -> str:
    return str(getattr(_tls, "obs_log_profile", "standard") or "standard").strip().lower()


def prime_obs_log_profile_for_chat(profile: str) -> None:
    """在单次对话流上设置 ``obs.log_profile`` 镜像（HTTP 入口调用）。"""

    _tls.obs_log_profile = str(profile or "standard").strip().lower()


def clear_obs_log_profile_tls() -> None:
    """对话结束清理线程局部（HTTP ``finally`` 调用）。"""

    for attr in ("obs_log_profile", "react_tool_step"):
        if hasattr(_tls, attr):
            delattr(_tls, attr)


def _tool_chain_log_level(profile: str) -> int:
    """``minimal`` 时 maint 子系统 handler 为 WARNING，故工具链用 WARNING 保证落 maint。"""

    if profile.strip().lower() == "minimal":
        return logging.WARNING
    return logging.INFO


def param_digest_for_log(
    profile: str,
    tool_name: str,
    arguments: Mapping[str, Any] | None,
) -> str:
    """工具参数摘要：脱敏 + 按档位截断（Obs O3 / O5）。"""

    _ = tool_name
    prof = (profile or "standard").strip().lower()
    limit = 4000 if prof == "audit" else 240
    parts: list[str] = []
    for k, v in sorted((arguments or {}).items()):
        key = str(k)
        if _SENSITIVE_KEY.search(key):
            parts.append(f"{key}=<redacted>")
            continue
        if isinstance(v, (dict, list)):
            s = json.dumps(
                v,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            s = str(v)
        if len(s) > limit:
            s = s[: limit - 3] + "..."
        parts.append(f"{key}={s}")
    body = "; ".join(parts) if parts else "(no-args)"
    if len(body) > limit + 80:
        return body[: limit] + "..."
    return body


def emit_tool_chain_v1(
    *,
    step_index: int,
    tool_name: str,
    elapsed_ms: int,
    status: str,
    param_digest: str,
    error_class: str | None,
) -> None:
    """写入一条工具链 JSON（作为 ``LogRecord.getMessage()`` 的完整正文）。"""

    profile = current_obs_profile()
    level = _tool_chain_log_level(profile)
    log = logging.getLogger("logos.agent.tool_chain")
    payload = {
        FIELD_EVENT: TOOL_CHAIN_EVENT_V1,
        FIELD_STEP_INDEX: int(step_index),
        FIELD_TOOL_NAME: str(tool_name),
        FIELD_ELAPSED_MS: int(elapsed_ms),
        FIELD_STATUS: str(status),
        FIELD_PARAM_DIGEST: str(param_digest)[:8000],
        FIELD_ERROR_CLASS: error_class,
    }
    line = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    log.log(level, line)


def classify_tool_observation(obs: str) -> tuple[str, str | None]:
    """由工具返回文本推断 ``status`` / ``error_class``（与内置、MCP 共用）。"""

    s = obs or ""
    if "被 S&G 策略拒绝" in s or "不在白名单" in s:
        return "denied", "GuardedToolDenied"
    if s.startswith("error:"):
        return "error", "ToolReturnedError"
    return "ok", None
