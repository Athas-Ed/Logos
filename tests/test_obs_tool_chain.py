"""Obs：工具调用链 JSON（S8～S10 / Obs O2、O5）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from logos.harness.obs import configure_logging
from logos.harness.obs.tool_chain import (
    TOOL_CHAIN_EVENT_V1,
    clear_obs_log_profile_tls,
    emit_tool_chain_v1,
    param_digest_for_log,
    prime_obs_log_profile_for_chat,
    reset_react_tool_steps,
)
from logos.ports import AppSettings


def _parse_inner_message_json(maint_line: str) -> dict:
    outer = json.loads(maint_line)
    return json.loads(outer["消息"])


def test_emit_tool_chain_frozen_keys_json_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_root = tmp_path / "logs_obs"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {log_root.as_posix()}\n",
        encoding="utf-8",
    )
    (cfg / "logging.yaml").write_text("logging:\n  format: json\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    configure_logging(
        AppSettings(
            workspace_root=".",
            example_ksfs_root=".",
            ksfs_root=".",
            index_root=".",
            logs_root=str(log_root),
            hsi_sqlite_path=".",
            chroma_persist_directory=".",
            chroma_collection="c",
            embedding_provider="p",
            embedding_model_path="m",
            obs_log_profile="standard",
        )
    )
    prime_obs_log_profile_for_chat("standard")
    reset_react_tool_steps()
    try:
        emit_tool_chain_v1(
            step_index=1,
            tool_name="retrieve",
            elapsed_ms=12,
            status="ok",
            param_digest="text=…",
            error_class=None,
        )
    finally:
        reset_react_tool_steps()
        clear_obs_log_profile_tls()

    agent_log = log_root / "maint" / "agent.log"
    assert agent_log.is_file()
    line = agent_log.read_text(encoding="utf-8").strip().splitlines()[-1]
    inner = _parse_inner_message_json(line)
    assert inner["event"] == TOOL_CHAIN_EVENT_V1
    assert inner["step_index"] == 1
    assert inner["tool_name"] == "retrieve"
    assert inner["elapsed_ms"] == 12
    assert inner["status"] == "ok"
    assert inner["param_digest"] == "text=…"
    assert inner["error_class"] is None


@pytest.mark.parametrize(
    ("profile", "expected_cn_level"),
    [
        ("standard", "信息"),
        ("verbose", "信息"),
        ("audit", "信息"),
        ("minimal", "警告"),
    ],
)
def test_tool_chain_log_level_by_obs_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile: str,
    expected_cn_level: str,
) -> None:
    """O5：minimal 时工具链用 WARNING，以便写入 maint（maint handler 为 WARNING）。"""
    log_root = tmp_path / f"logs_{profile}"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {log_root.as_posix()}\n",
        encoding="utf-8",
    )
    (cfg / "logging.yaml").write_text("logging:\n  format: json\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    configure_logging(
        AppSettings(
            workspace_root=".",
            example_ksfs_root=".",
            ksfs_root=".",
            index_root=".",
            logs_root=str(log_root),
            hsi_sqlite_path=".",
            chroma_persist_directory=".",
            chroma_collection="c",
            embedding_provider="p",
            embedding_model_path="m",
            obs_log_profile=profile,
        )
    )
    prime_obs_log_profile_for_chat(profile)
    try:
        emit_tool_chain_v1(
            step_index=1,
            tool_name="echo",
            elapsed_ms=0,
            status="ok",
            param_digest="(no-args)",
            error_class=None,
        )
    finally:
        clear_obs_log_profile_tls()

    agent_log = log_root / "maint" / "agent.log"
    assert agent_log.is_file()
    line = agent_log.read_text(encoding="utf-8").strip().splitlines()[-1]
    outer = json.loads(line)
    assert outer["级别"] == expected_cn_level
    inner = json.loads(outer["消息"])
    assert inner["event"] == TOOL_CHAIN_EVENT_V1


def test_param_digest_redacts_sensitive_keys() -> None:
    d = param_digest_for_log(
        "standard",
        "t",
        {"text": "hello", "api_key": "SECRET", "nested": {"x": 1}},
    )
    assert "SECRET" not in d
    assert "<redacted>" in d
    assert "hello" in d


def test_tool_chain_written_to_daily_even_when_maint_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """日常轨 daily 仍接收 INFO（minimal 下亦可检索工具链）。"""
    log_root = tmp_path / "logs_daily"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {log_root.as_posix()}\n",
        encoding="utf-8",
    )
    (cfg / "logging.yaml").write_text("logging:\n  format: json\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    configure_logging(
        AppSettings(
            workspace_root=".",
            example_ksfs_root=".",
            ksfs_root=".",
            index_root=".",
            logs_root=str(log_root),
            hsi_sqlite_path=".",
            chroma_persist_directory=".",
            chroma_collection="c",
            embedding_provider="p",
            embedding_model_path="m",
            obs_log_profile="minimal",
        )
    )
    prime_obs_log_profile_for_chat("minimal")
    try:
        emit_tool_chain_v1(
            step_index=2,
            tool_name="read_ksfs",
            elapsed_ms=3,
            status="ok",
            param_digest="path=x.md",
            error_class=None,
        )
    finally:
        clear_obs_log_profile_tls()

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    daily = log_root / "daily" / ym / f"{day}.log"
    assert daily.is_file()
    found = False
    for ln in daily.read_text(encoding="utf-8").splitlines():
        if TOOL_CHAIN_EVENT_V1 in ln and "read_ksfs" in ln:
            found = True
            break
    assert found
