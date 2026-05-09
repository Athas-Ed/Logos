"""Stream 1: config merge / env overrides and Obs logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from logos.harness.config import (
    apply_env_overrides,
    deep_merge,
    load_app_settings,
    load_merged_config_dict,
    merged_dict_to_app_settings,
    resolve_config_dir,
)
from logos.harness.obs import configure_logging


def test_deep_merge_nested() -> None:
    base = {"paths": {"a": 1, "b": 2}, "x": 0}
    over = {"paths": {"b": 3}, "x": 9}
    assert deep_merge(base, over) == {"paths": {"a": 1, "b": 3}, "x": 9}


def test_apply_env_overrides_nested() -> None:
    tree: dict = {"paths": {"logs_root": "./logs"}}
    env = {"LOGOS_PATHS__LOGS_ROOT": "/tmp/logos_logs"}
    apply_env_overrides(tree, environ=env)
    assert tree["paths"]["logs_root"] == "/tmp/logos_logs"


def test_apply_env_skips_empty_and_config_dir() -> None:
    tree: dict = {"paths": {"logs_root": "./logs"}}
    env = {
        "LOGOS_PATHS__WORKSPACE_ROOT": "",
        "LOGOS_CONFIG_DIR": "/should/not/appear",
    }
    apply_env_overrides(tree, environ=env)
    assert "config_dir" not in tree
    assert tree["paths"]["logs_root"] == "./logs"


def test_resolve_config_dir_explicit(tmp_path: Path) -> None:
    d = tmp_path / "config"
    d.mkdir()
    (d / "defaults.yaml").write_text("paths:\n  logs_root: ./x\n", encoding="utf-8")
    assert resolve_config_dir(d).resolve() == d.resolve()


def test_load_merged_from_repo_config() -> None:
    repo = Path(__file__).resolve().parents[1]
    cfg = repo / "config"
    data = load_merged_config_dict(cfg, environ={})
    assert data["paths"]["logs_root"] == "./logs"
    s = merged_dict_to_app_settings(data)
    assert s.logs_root == "./logs"


def test_env_overrides_logs_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./from_defaults\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGOS_PATHS__LOGS_ROOT", str(tmp_path / "env_logs"))
    s = load_app_settings(cfg)
    assert s.logs_root == str(tmp_path / "env_logs")


def test_configure_logging_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_root = tmp_path / "logs_out"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {log_root.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOGOS_CONFIG_DIR", raising=False)
    # Point resolver at our tmp config (cwd has no defaults.yaml parent walk)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    from logos.ports import AppSettings

    settings = AppSettings(
        workspace_root=".",
        example_ksfs_root=".",
        index_root=".",
        logs_root=str(log_root),
        hsi_sqlite_path=".",
        chroma_persist_directory=".",
        chroma_collection="c",
        embedding_provider="p",
        embedding_model_path="m",
    )
    configure_logging(settings)
    log = logging.getLogger("logos.test")
    log.info("hello_stream1")
    assert (log_root / "logos.log").is_file()
    text = (log_root / "logos.log").read_text(encoding="utf-8")
    assert "hello_stream1" in text
