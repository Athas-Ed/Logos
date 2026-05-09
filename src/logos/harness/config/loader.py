from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from logos.ports import AppSettings

_ENV_PREFIX = "LOGOS_"


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """递归合并：在 *base* 的副本上叠 *override*；子字典继续递归，否则覆盖。"""
    out: dict[str, Any] = dict(base)
    for key, val in override.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(val, Mapping)
        ):
            out[key] = deep_merge(out[key], val)  # type: ignore[arg-type]
        else:
            out[key] = val
    return out


def _set_nested(target: dict[str, Any], segments: list[str], value: str) -> None:
    node = target
    for seg in segments[:-1]:
        child = node.get(seg)
        if not isinstance(child, dict):
            child = {}
            node[seg] = child
        node = child
    node[segments[-1]] = value


def apply_env_overrides(tree: dict[str, Any], environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """将 ``LOGOS_*`` 环境变量写入嵌套配置 *tree*（原地修改）。

    命名规则：``LOGOS_<段>__<键>`` → ``tree[段小写][键小写]``，段之间用 ``__``。
    单独一段 ``LOGOS_OPERATING_MODE`` 写入顶层 ``operating_mode``。
    空字符串的环境变量会被跳过。
    """
    env = environ if environ is not None else os.environ
    for raw_name, raw_val in env.items():
        if not raw_name.startswith(_ENV_PREFIX) or raw_val == "":
            continue
        if raw_name == "LOGOS_CONFIG_DIR":
            continue
        body = raw_name[len(_ENV_PREFIX) :]
        segments = [s.lower() for s in body.split("__") if s]
        if not segments:
            continue
        _set_nested(tree, segments, raw_val)
    return tree


def resolve_config_dir(
    explicit: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """返回存放 ``defaults.yaml``（及可选 ``local.yaml``）的配置目录。

    解析顺序：
    1. 若传入 *explicit*，直接使用其路径。
    2. 否则看环境变量 ``LOGOS_CONFIG_DIR``（*environ* 或 ``os.environ``）。
    3. 否则从当前工作目录向上查找存在 ``config/defaults.yaml`` 的目录。
    4. 都找不到则返回 ``当前目录/config``（可能尚不存在，由调用方处理）。
    """
    env = environ if environ is not None else os.environ
    if explicit is not None:
        return Path(explicit).resolve()
    env_dir = env.get("LOGOS_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    cwd = Path.cwd()
    for base in [cwd, *cwd.parents]:
        candidate = base / "config" / "defaults.yaml"
        if candidate.is_file():
            return (base / "config").resolve()
    return (cwd / "config").resolve()


def load_yaml_dict(path: Path) -> dict[str, Any]:
    """读取 YAML 文件为字典；文件不存在返回空字典；根非 dict 则抛 ValueError。"""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"YAML 根节点必须是键值映射（mapping），文件：{path}"
        raise ValueError(msg)
    return data


def load_merged_config_dict(
    config_dir: Path | str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """加载 ``defaults.yaml`` + ``local.yaml`` + 可选 ``logging.yaml``，再应用环境变量覆盖。

    ``logging.yaml`` 可省略（不存在则忽略），用于在不改 ``defaults.yaml`` 的前提下调节日志等。
    """
    root = resolve_config_dir(config_dir, environ=environ)
    defaults = load_yaml_dict(root / "defaults.yaml")
    local = load_yaml_dict(root / "local.yaml")
    merged = deep_merge(defaults, local)
    logging_overlay = load_yaml_dict(root / "logging.yaml")
    merged = deep_merge(merged, logging_overlay)
    return apply_env_overrides(merged, environ=environ)


def merged_dict_to_app_settings(data: Mapping[str, Any]) -> AppSettings:
    paths = data.get("paths") or {}
    emb = data.get("embeddings") or {}
    chroma = data.get("chroma") or {}
    return AppSettings(
        workspace_root=str(paths.get("workspace_root", "./workspace")),
        example_ksfs_root=str(paths.get("example_ksfs_root", "./example_ksfs")),
        index_root=str(paths.get("index_root", "./.index")),
        logs_root=str(paths.get("logs_root", "./logs")),
        hsi_sqlite_path=str(paths.get("hsi_sqlite_path", "./.index/.high-speed_index")),
        chroma_persist_directory=str(
            chroma.get("persist_directory", "./.index/.vector_index")
        ),
        chroma_collection=str(chroma.get("collection", "lkc_chunks_v0")),
        embedding_provider=str(emb.get("provider", "bge_small_zh")),
        embedding_model_path=str(
            emb.get("model_path", "models/tooling/embeddings/bge-small-zh-v1.5")
        ),
        operating_mode=str(data.get("operating_mode", "author")),
    )


def load_app_settings(
    config_dir: Path | str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> AppSettings:
    """合并 YAML 与环境变量后，返回 :class:`~logos.ports.AppSettings`。"""
    return merged_dict_to_app_settings(
        load_merged_config_dict(config_dir, environ=environ)
    )
