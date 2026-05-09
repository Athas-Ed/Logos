from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Final

# 文本行格式：时间、级别（中文）、记录器名、消息正文
TEXT_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(name)s：%(message)s"

_LEVEL_TO_CN: Final[dict[str, str]] = {
    "DEBUG": "调试",
    "INFO": "信息",
    "WARNING": "警告",
    "ERROR": "错误",
    "CRITICAL": "严重",
}

_STANDARD_LOGRECORD_KEYS: frozenset[str] | None = None


def _standard_logrecord_keys() -> frozenset[str]:
    global _STANDARD_LOGRECORD_KEYS
    if _STANDARD_LOGRECORD_KEYS is None:
        sample = logging.LogRecord(
            name="n",
            level=0,
            pathname="",
            lineno=0,
            msg="m",
            args=(),
            exc_info=None,
        )
        _STANDARD_LOGRECORD_KEYS = frozenset(sample.__dict__)
    return _STANDARD_LOGRECORD_KEYS


def _level_display(levelname: str) -> str:
    return _LEVEL_TO_CN.get(levelname, levelname)


class TextLineFormatter(logging.Formatter):
    """文本行日志：级别名显示为中文（DEBUG→调试 等）。"""

    def format(self, record: logging.LogRecord) -> str:
        saved = record.levelname
        record.levelname = _level_display(saved)
        try:
            return super().format(record)
        finally:
            record.levelname = saved


def log_record_to_payload(record: logging.LogRecord) -> dict[str, Any]:
    """构造 JSON 行日志用的字典（键名为中文，便于阅读）。"""
    ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
    out: dict[str, Any] = {
        "时间": ts,
        "级别": _level_display(record.levelname),
        "记录器": record.name,
        "消息": record.getMessage(),
    }
    if record.exc_info:
        out["异常"] = logging.Formatter().formatException(record.exc_info).rstrip("\n")
    std = _standard_logrecord_keys()
    extras = {
        k: record.__dict__[k]
        for k in record.__dict__
        if k not in std and not k.startswith("_")
    }
    if extras:
        safe: dict[str, Any] = {}
        for k, v in extras.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                safe[k] = v
            else:
                safe[k] = str(v)
        out["扩展"] = safe
    return out


class JsonLineFormatter(logging.Formatter):
    """每行一条 JSON（UTF-8，ensure_ascii=False）。"""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(log_record_to_payload(record), ensure_ascii=False)


def make_formatter(style: str) -> logging.Formatter:
    """按 *style* 返回格式化器：``text`` 为中文级别文本行，``json`` 为 JSON 行。"""
    key = (style or "text").strip().lower()
    if key == "json":
        return JsonLineFormatter()
    return TextLineFormatter(TEXT_FORMAT)
