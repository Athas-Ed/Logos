"""paths.CONVERSATIONS_CACHE 配置与 bootstrap 暴露。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from logos.platform.config.loader import load_merged_config_dict, merged_dict_to_app_settings
from logos.platform.config.paths_resolve import resolve_conversations_cache_abs
from logos.platform.ii_layer.app import create_app
from logos.platform.ii_layer.container import AppPorts
from tests.test_stream5_api import _make_ports


def test_defaults_yaml_has_conversations_cache() -> None:
    repo = Path(__file__).resolve().parents[1]
    defaults = yaml.safe_load((repo / "config" / "defaults.yaml").read_text(encoding="utf-8"))
    assert defaults["paths"]["CONVERSATIONS_CACHE"] == "./workspace/conversations"


def test_merged_config_reads_conversations_cache(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text(
        "paths:\n  CONVERSATIONS_CACHE: ./custom_conv\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))
    data = load_merged_config_dict(cfg)
    settings = merged_dict_to_app_settings(data)
    assert settings.conversations_cache == "./custom_conv"


def test_env_overrides_conversations_cache(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "defaults.yaml").write_text("paths: {}\n", encoding="utf-8")
    monkeypatch.setenv("LOGOS_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("LOGOS_PATHS__CONVERSATIONS_CACHE", "./from_env")
    data = load_merged_config_dict(cfg)
    settings = merged_dict_to_app_settings(data)
    assert settings.conversations_cache == "./from_env"


def test_bootstrap_conversations_cache_root(tmp_path: Path, monkeypatch) -> None:
    conv_rel = "./workspace/conversations"
    ports = _make_ports(tmp_path)
    ports = AppPorts(
        settings=replace(ports.settings, conversations_cache=conv_rel),
        llm=ports.llm,
        retrieval=ports.retrieval,
        knowledge_source=ports.knowledge_source,
        metadata_index=ports.metadata_index,
        semantic_store=ports.semantic_store,
        text_embedder=ports.text_embedder,
        developer=ports.developer,
    )
    monkeypatch.setattr(
        "logos.platform.mcp_stdio.resolve_repo_root",
        lambda: tmp_path,
    )
    app = create_app(ports)
    with TestClient(app) as client:
        r = client.get("/api/v1/bootstrap")
    assert r.status_code == 200
    expected = str(resolve_conversations_cache_abs(tmp_path, conv_rel))
    assert r.json()["conversations_cache_root"] == expected


def test_resolve_conversations_cache_abs_relative() -> None:
    repo = Path("/repo")
    assert resolve_conversations_cache_abs(repo, "./workspace/conversations") == (
        repo / "workspace" / "conversations"
    ).resolve()
