"""Stream 1：在临时 ``logs/_pytest/`` 下验证自动建目录与文件日志。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from logos.harness.obs import configure_logging, get_obs_logger


def test_logs_subdir_auto_created_and_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """使用 ``logs/_pytest/`` 子目录，避免写入仓库根 ``./logs``。"""
    logs_root = tmp_path / "logs" / "_pytest"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {logs_root.as_posix()}\n",
        encoding="utf-8",
    )
    (cfg / "logging.yaml").write_text(
        "logging:\n  format: text\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    configure_logging(log_format="text")
    get_obs_logger("pytest").info("子目录日志探针")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    log_file = logs_root / "daily" / ym / f"{day}.log"
    assert log_file.is_file()
    text = log_file.read_text(encoding="utf-8")
    assert "子目录日志探针" in text
    assert "信息" in text or "INFO" in text
