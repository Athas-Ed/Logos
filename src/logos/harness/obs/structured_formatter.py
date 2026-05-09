from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Final

TEXT_FORMAT: Final[str] = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

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


def log_record_to_payload(record: logging.LogRecord) -> dict[str, Any]:
    """Build a JSON-serializable dict for structured logging."""
    ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
    out: dict[str, Any] = {
        "timestamp": ts,
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    if record.exc_info:
        out["exception"] = logging.Formatter().formatException(record.exc_info).rstrip("\n")
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
        out["extra"] = safe
    return out


class JsonLineFormatter(logging.Formatter):
    """One JSON object per log line (UTF-8 safe, ``ensure_ascii=False``)."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(log_record_to_payload(record), ensure_ascii=False)


def make_formatter(style: str) -> logging.Formatter:
    """Return a formatter for ``style`` ``text`` (classic line) or ``json`` (JSON lines)."""
    key = (style or "text").strip().lower()
    if key == "json":
        return JsonLineFormatter()
    return logging.Formatter(TEXT_FORMAT)
