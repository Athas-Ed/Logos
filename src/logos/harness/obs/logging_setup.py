from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from logos.harness.config import load_app_settings
from logos.ports import AppSettings

_DEFAULT_FORMAT: Final[str] = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_FILE_NAME: Final[str] = "logos.log"


def _ensure_log_dir(logs_root: str | Path) -> Path:
    root = Path(logs_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def configure_logging(
    settings: AppSettings | None = None,
    *,
    level: int = logging.INFO,
    log_file_name: str = _FILE_NAME,
) -> AppSettings:
    """Configure the ``logos`` logger tree: console + file under ``settings.logs_root``.

    If *settings* is omitted, loads merged config via :func:`logos.harness.config.load_app_settings`
    (so ``paths.logs_root`` from ``defaults.yaml`` / ``local.yaml`` / env applies).

    Idempotent: existing ``logos`` handlers of the same types are cleared before attach.
    Returns the :class:`~logos.ports.AppSettings` used (loaded or passed in).
    """
    resolved = settings if settings is not None else load_app_settings()
    log_dir = _ensure_log_dir(resolved.logs_root)
    file_path = log_dir / log_file_name

    logos_logger = logging.getLogger("logos")
    logos_logger.setLevel(level)
    logos_logger.propagate = False

    formatter = logging.Formatter(_DEFAULT_FORMAT)

    for h in list(logos_logger.handlers):
        logos_logger.removeHandler(h)

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    logos_logger.addHandler(stream)

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logos_logger.addHandler(file_handler)

    return resolved
