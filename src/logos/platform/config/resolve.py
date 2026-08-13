"""config 层统一路径解析：``ResolvedPaths`` 是所有配置路径的唯一解析出口。

架构约束（架构评审 Q3a/Q3b）：
- **本模块是 ``src/logos`` 中唯一 import ``resolve_repo_root`` 的地方**；
- 所有消费方（HTTP handler、组合根、S&G factory、资源定位）从这里取已解析路径，
  禁止自行 ``Path(settings.*).resolve()`` 或 ``resolve_repo_root()``；
- ``original_scripts/check_path_resolve_discipline.py``（pre-commit，开发自用）守卫上述两条纪律。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from logos.ports.settings import AppSettings

from .paths_resolve import resolve_under_repo


@dataclass(frozen=True, slots=True)
class ResolvedPaths:
    """配置路径解析为绝对路径后的只读快照。"""

    repo_root: Path
    workspace_root: Path
    example_ksfs_root: Path
    ksfs_root: Path
    index_root: Path
    logs_root: Path
    conversations_cache: Path
    hsi_sqlite_path: Path
    chroma_persist_directory: Path
    kg_db_path: Path
    sparse_db_path: Path
    #: ``config/local.yaml`` 所在目录（写入 API Key 等运行时配置用）
    config_dir: Path
    #: 资源定位（相对仓库根，非用户配置）
    prompts_root: Path
    skills_manifests_root: Path
    entity_template_root: Path
    pipelines_root: Path


def resolved_repo_root() -> Path:
    """仓库根（唯一经 config 层暴露；按属性访问以支持测试 monkeypatch）。"""
    import logos.platform.mcp_stdio as _mcp_stdio

    return _mcp_stdio.resolve_repo_root()


def prompts_root() -> Path:
    return resolved_repo_root() / "resources" / "prompts"


def skills_manifests_root() -> Path:
    return resolved_repo_root() / "skills" / "manifests"


def entity_template_root() -> Path:
    return resolved_repo_root() / "resources" / "entity_template"


def pipelines_root() -> Path:
    return resolved_repo_root() / "resources" / "pipelines"


def _resolve_config_dir(repo_root: Path) -> Path:
    env_dir = (os.environ.get("LOGOS_CONFIG_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).resolve()
    return (repo_root / "config").resolve()


def resolve_app_paths(settings: AppSettings) -> ResolvedPaths:
    """将 :class:`~logos.ports.AppSettings` 中的全部路径解析为绝对路径。

    *settings* 保持原始字符串不动；解析结果仅存在于 :class:`ResolvedPaths`。
    """
    repo = resolved_repo_root()
    return ResolvedPaths(
        repo_root=repo,
        workspace_root=resolve_under_repo(repo, settings.workspace_root),
        example_ksfs_root=resolve_under_repo(repo, settings.example_ksfs_root),
        ksfs_root=resolve_under_repo(repo, settings.ksfs_root),
        index_root=resolve_under_repo(repo, settings.index_root),
        logs_root=resolve_under_repo(repo, settings.logs_root),
        conversations_cache=resolve_under_repo(repo, settings.conversations_cache),
        hsi_sqlite_path=resolve_under_repo(repo, settings.hsi_sqlite_path),
        chroma_persist_directory=resolve_under_repo(
            repo, settings.chroma_persist_directory
        ),
        kg_db_path=resolve_under_repo(repo, settings.kg_db_path),
        sparse_db_path=resolve_under_repo(repo, settings.sparse_db_path),
        config_dir=_resolve_config_dir(repo),
        prompts_root=prompts_root(),
        skills_manifests_root=skills_manifests_root(),
        entity_template_root=entity_template_root(),
        pipelines_root=pipelines_root(),
    )
