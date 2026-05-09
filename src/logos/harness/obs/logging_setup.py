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
    """若不存在则创建 ``settings.logs_root``（含父目录），返回解析后的路径。"""
    root = Path(settings.logs_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_obs_logger(name: str = "") -> logging.Logger:
    """取得 ``logos`` 命名空间下的记录器；例如 ``get_obs_logger("api")`` → ``logos.api``。"""
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
    """配置 ``logos`` 根记录器：控制台 + 写入 ``settings.logs_root`` 下的日志文件。

    会加载合并后的 YAML（含可选 ``logging.yaml``）以决定格式与文件名；
    若省略 *settings*，则从上述合并结果构造 :class:`~logos.ports.AppSettings`。

    *log_file_name* / *log_format* 非 ``None`` 时覆盖 YAML（取值 ``text`` / ``json``）。

    幂等：会先移除 ``logos`` 上已有 handler 再挂载新的。
    返回实际使用的 :class:`~logos.ports.AppSettings`。
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
