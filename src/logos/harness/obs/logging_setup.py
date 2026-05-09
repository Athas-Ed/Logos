from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from logos.harness.config import load_merged_config_dict, merged_dict_to_app_settings
from logos.harness.obs.structured_formatter import make_formatter
from logos.ports import AppSettings

_FILE_NAME: Final[str] = "logos.log"


def ensure_logs_directory(settings: AppSettings) -> Path:
    """Create ``settings.logs_root`` (and parents) if missing; return resolved path."""
    root = Path(settings.logs_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_obs_logger(name: str = "") -> logging.Logger:
    """Logger under the ``logos`` namespace (e.g. ``get_obs_logger("api")`` → ``logos.api``)."""
    qual = "logos" if not name.strip() else f"logos.{name.strip()}"
    return logging.getLogger(qual)


def configure_logging(
    settings: AppSettings | None = None,
    *,
    config_dir: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    level: int = logging.INFO,
    log_file_name: str | None = None,
    log_format: str | None = None,
) -> AppSettings:
    """Configure the ``logos`` logger tree: console + file under ``settings.logs_root``.

    Loads merged YAML (including optional ``logging.yaml``) once for format / filename;
    if *settings* is omitted, builds :class:`~logos.ports.AppSettings` from that merge.

    *log_file_name* / *log_format* override YAML when not ``None`` (values: ``text`` / ``json``).

    Idempotent: clears existing ``logos`` handlers before attaching new ones.
    Returns the :class:`~logos.ports.AppSettings` used.
    """
    merged = load_merged_config_dict(config_dir, environ=environ)
    resolved = merged_dict_to_app_settings(merged) if settings is None else settings

    log_cfg = merged.get("logging") if isinstance(merged.get("logging"), dict) else {}
    eff_file = (
        log_file_name
        if log_file_name is not None
        else str(log_cfg.get("file_name") or _FILE_NAME)
    )
    eff_format = (
        log_format
        if log_format is not None
        else str(log_cfg.get("format") or "text")
    )

    log_dir = ensure_logs_directory(resolved)
    file_path = log_dir / eff_file
    formatter = make_formatter(eff_format)

    logos_logger = logging.getLogger("logos")
    logos_logger.setLevel(level)
    logos_logger.propagate = False

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
