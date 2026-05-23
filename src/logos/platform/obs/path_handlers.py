"""Obs 落盘：日常按 ``daily/YYYY-MM/YYYY-MM-DD.log``；维护按 ``maint/<子系统>.log``。"""

from __future__ import annotations

import io
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Final

_LOG_LINE_END: Final[str] = "\n"


def _utc_date_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_month_dir() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class DailyDirectoryFileHandler(logging.Handler):
    """写入 ``<logs_root>/daily/YYYY-MM/YYYY-MM-DD.log``；仅记录 ``>= INFO``。"""

    def __init__(self, logs_root: Path, *, encoding: str = "utf-8") -> None:
        super().__init__(level=logging.INFO)
        self.logs_root = Path(logs_root)
        self.encoding = encoding
        self._lock = threading.RLock()
        self._stream: io.TextIOWrapper | None = None
        self._active_key: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.INFO:
            return
        try:
            msg = self.format(record)
            line = msg + _LOG_LINE_END
        except Exception:
            self.handleError(record)
            return
        with self._lock:
            try:
                key = _utc_date_key()
                if key != self._active_key:
                    if self._stream is not None:
                        self._stream.close()
                        self._stream = None
                    month = _utc_month_dir()
                    day_dir = self.logs_root / "daily" / month
                    day_dir.mkdir(parents=True, exist_ok=True)
                    path = day_dir / f"{key}.log"
                    self._stream = path.open("a", encoding=self.encoding)
                    self._active_key = key
                assert self._stream is not None
                self._stream.write(line)
                self._stream.flush()
            except Exception:
                self.handleError(record)

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._active_key = None
        super().close()


class MaintSubsystemFileHandler(logging.Handler):
    """写入 ``<logs_root>/maint/<name>.log``；按 logger 名最长前缀匹配子系统。"""

    ROUTES: ClassVar[tuple[tuple[str, str], ...]] = (
        ("logos.platform.mcp", "mcp.log"),
        ("logos.infrastructure.llm", "llm.log"),
        ("logos.api", "api.log"),
        ("logos.agent", "agent.log"),
        ("logos.retrieval", "retrieval.log"),
        ("logos.persistence", "persistence.log"),
        ("logos.platform", "platform.log"),
    )

    def __init__(self, logs_root: Path, *, encoding: str = "utf-8") -> None:
        super().__init__()
        self.maint_root = Path(logs_root) / "maint"
        self.maint_root.mkdir(parents=True, exist_ok=True)
        self.encoding = encoding
        self._lock = threading.RLock()
        self._streams: dict[str, io.TextIOWrapper] = {}

    @staticmethod
    def _logger_matches_prefix(logger_name: str, prefix: str) -> bool:
        return logger_name == prefix or logger_name.startswith(f"{prefix}.")

    @staticmethod
    def target_filename(logger_name: str) -> str:
        for prefix, fname in MaintSubsystemFileHandler.ROUTES:
            if MaintSubsystemFileHandler._logger_matches_prefix(logger_name, prefix):
                return fname
        return "core.log"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            line = msg + _LOG_LINE_END
        except Exception:
            self.handleError(record)
            return
        fname = self.target_filename(record.name)
        path = self.maint_root / fname
        key = str(path.resolve())
        with self._lock:
            try:
                if key not in self._streams:
                    self._streams[key] = path.open("a", encoding=self.encoding)
                self._streams[key].write(line)
                self._streams[key].flush()
            except Exception:
                self.handleError(record)

    def close(self) -> None:
        with self._lock:
            for stream in self._streams.values():
                try:
                    stream.close()
                except Exception:
                    pass
            self._streams.clear()
        super().close()
