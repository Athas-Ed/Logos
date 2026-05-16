"""Stream 1：配置合并、环境变量覆盖与 Obs 日志。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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
from logos.harness.obs import configure_logging, get_obs_logger


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
    assert data.get("logging", {}).get("format") == "json"
    s = merged_dict_to_app_settings(data)
    assert s.logs_root == "./logs"
    assert isinstance(s.mcp_servers, tuple)


def test_obs_show_log_root_in_gui_from_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./logs\n  workspace_root: ./w\n"
        "  example_ksfs_root: ./e\n  ksfs_root: ./k\n  index_root: ./i\n"
        "  hsi_sqlite_path: ./h\n"
        "obs:\n  show_log_root_in_gui: true\n",
        encoding="utf-8",
    )
    s = load_app_settings(cfg)
    assert s.obs_show_log_root_in_gui is True


def test_mcp_servers_from_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./logs\n  workspace_root: ./w\n"
        "  example_ksfs_root: ./e\n  ksfs_root: ./k\n  index_root: ./i\n"
        "  hsi_sqlite_path: ./h\n"
        "skills:\n"
        "  mcp_servers:\n"
        "    - id: a\n"
        "      enabled: true\n"
        "      entrypoint: skills/x/server.py\n"
        "      strip_http_proxy: true\n"
        "      env:\n"
        "        FOO: bar\n",
        encoding="utf-8",
    )
    s = load_app_settings(cfg)
    assert len(s.mcp_servers) == 1
    e = s.mcp_servers[0]
    assert e.id == "a"
    assert e.enabled is True
    assert e.entrypoint == "skills/x/server.py"
    assert e.strip_http_proxy is True
    assert ("FOO", "bar") in e.env


def test_mcp_servers_enabled_defaults_true_when_omitted(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./logs\n  workspace_root: ./w\n"
        "  example_ksfs_root: ./e\n  ksfs_root: ./k\n  index_root: ./i\n"
        "  hsi_sqlite_path: ./h\n"
        "skills:\n"
        "  mcp_servers:\n"
        "    - id: no_enabled_key\n"
        "      entrypoint: skills/x/server.py\n",
        encoding="utf-8",
    )
    s = load_app_settings(cfg)
    assert len(s.mcp_servers) == 1
    assert s.mcp_servers[0].enabled is True


def test_mcp_servers_must_be_yaml_list(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./logs\n  workspace_root: ./w\n"
        "  example_ksfs_root: ./e\n  ksfs_root: ./k\n  index_root: ./i\n"
        "  hsi_sqlite_path: ./h\n"
        "skills:\n  mcp_servers: not_a_list\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mcp_servers"):
        load_app_settings(cfg)


def test_logging_yaml_layer_merges(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text("paths:\n  logs_root: ./a\n", encoding="utf-8")
    (cfg / "logging.yaml").write_text(
        "logging:\n  format: json\n  file_name: x.log\n",
        encoding="utf-8",
    )
    data = load_merged_config_dict(cfg, environ={})
    assert data["paths"]["logs_root"] == "./a"
    assert data["logging"]["format"] == "json"
    assert data["logging"]["file_name"] == "x.log"


def test_local_yaml_overrides_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  logs_root: ./from_defaults\n  workspace_root: ./w1\n",
        encoding="utf-8",
    )
    (cfg / "local.yaml").write_text(
        "paths:\n  logs_root: ./from_local\n",
        encoding="utf-8",
    )
    data = load_merged_config_dict(cfg, environ={})
    assert data["paths"]["logs_root"] == "./from_local"
    assert data["paths"]["workspace_root"] == "./w1"
    s = load_app_settings(cfg)
    assert s.logs_root == "./from_local"
    assert s.workspace_root == "./w1"


def test_env_overrides_logging_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text("paths:\n  logs_root: ./logs\n", encoding="utf-8")
    (cfg / "logging.yaml").write_text(
        "logging:\n  format: json\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGOS_LOGGING__FORMAT", "text")
    data = load_merged_config_dict(cfg, environ=None)
    assert data["logging"]["format"] == "text"


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
        ksfs_root=".",
        index_root=".",
        logs_root=str(log_root),
        hsi_sqlite_path=".",
        chroma_persist_directory=".",
        chroma_collection="c",
        embedding_provider="p",
        embedding_model_path="m",
    )
    configure_logging(settings)
    log = get_obs_logger("test")
    log.info("hello_stream1")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    daily = log_root / "daily" / ym / f"{day}.log"
    assert daily.is_file()
    text = daily.read_text(encoding="utf-8")
    assert "hello_stream1" in text
    maint = log_root / "maint" / "core.log"
    assert maint.is_file()
    assert "hello_stream1" in maint.read_text(encoding="utf-8")


def test_configure_logging_json_lines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_root = tmp_path / "logs_json"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        f"paths:\n  logs_root: {log_root.as_posix()}\n",
        encoding="utf-8",
    )
    (cfg / "logging.yaml").write_text(
        "logging:\n  format: json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))

    configure_logging(log_format="json")
    get_obs_logger("api").info("json_event")
    log_path = log_root / "maint" / "api.log"
    assert log_path.is_file()
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["消息"] == "json_event"
    assert payload["记录器"] == "logos.api"
