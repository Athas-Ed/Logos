from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from logos.harness.config import load_merged_config_dict, merged_dict_to_app_settings
from logos.harness.obs.path_handlers import DailyDirectoryFileHandler, MaintSubsystemFileHandler
from logos.harness.obs.structured_formatter import make_formatter
from logos.ports import AppSettings


def ensure_logs_directory(settings: AppSettings) -> Path:
    """若不存在则创建 ``settings.logs_root`` 及 ``daily/``、``maint/`` 占位，返回解析后的路径。"""
    root = Path(settings.logs_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "daily").mkdir(parents=True, exist_ok=True)
    (root / "maint").mkdir(parents=True, exist_ok=True)
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
    level: int | None = None,
    log_file_name: str | None = None,
    log_format: str | None = None,
) -> AppSettings:
    """配置 ``logos`` 根记录器：控制台 + 日常/维护分轨落盘。

    * **日常**：``<logs_root>/daily/YYYY-MM/YYYY-MM-DD.log``，固定 ``>= INFO``，与 ``obs.log_profile`` 解耦。
    * **维护**：``<logs_root>/maint/<子系统>.log``（api / mcp / agent / retrieval / llm / persistence / harness / core），级别随 ``obs.log_profile``（或 *level* 覆盖）。

    合并 YAML 中的 ``logging.format``（``text`` / ``json``）；``logging.file_name`` 已废弃，保留键不影响落盘路径。

    幂等：会先移除 ``logos`` 上已有 handler 再挂载新的。
    返回实际使用的 :class:`~logos.ports.AppSettings`。
    """
    _ = log_file_name  # 旧单文件参数，已废弃；保留签名兼容调用方
    merged = load_merged_config_dict(config_dir, environ=environ)
    resolved = merged_dict_to_app_settings(merged) if settings is None else settings

    log_cfg = merged.get("logging") if isinstance(merged.get("logging"), dict) else {}
    if level is None:
        profile = str(resolved.obs_log_profile or "standard").strip().lower()
        if profile == "minimal":
            maint_handler_level = logging.WARNING
            stream_level = logging.WARNING
        elif profile in ("verbose", "audit"):
            maint_handler_level = logging.DEBUG
            stream_level = logging.DEBUG
        else:
            maint_handler_level = logging.INFO
            stream_level = logging.INFO
    else:
        maint_handler_level = level
        stream_level = level

    eff_format = (
        log_format
        if log_format is not None
        else str(log_cfg.get("format") or "text")
    )

    log_root = ensure_logs_directory(resolved)
    formatter = make_formatter(eff_format)

    logos_logger = logging.getLogger("logos")
    # 子 logger 的 DEBUG 需能到达维护 Handler；由各级 Handler 再过滤
    logos_logger.setLevel(logging.DEBUG)
    logos_logger.propagate = False

    for h in list(logos_logger.handlers):
        logos_logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    stream = logging.StreamHandler()
    stream.setLevel(stream_level)
    stream.setFormatter(formatter)
    logos_logger.addHandler(stream)

    daily_handler = DailyDirectoryFileHandler(log_root)
    daily_handler.setFormatter(formatter)
    logos_logger.addHandler(daily_handler)

    maint_handler = MaintSubsystemFileHandler(log_root)
    maint_handler.setLevel(maint_handler_level)
    maint_handler.setFormatter(formatter)
    logos_logger.addHandler(maint_handler)

    return resolved
