from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from logos.ports import AppSettings

_ENV_PREFIX = "LOGOS_"


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base`` (dict values merge, else replace)."""
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
    """Apply ``LOGOS_*`` environment variables onto a nested config dict (in place).

    Naming: ``LOGOS_<section>__<key>`` → ``tree[section.lower()][key.lower()]`` with
    segment names lowercased and joined by ``__``. Single segment
    ``LOGOS_OPERATING_MODE`` sets top-level ``operating_mode``.
    Empty values are skipped.
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
    """Directory containing ``defaults.yaml`` (and optional ``local.yaml``).

    Resolution:
    1. ``explicit`` if given.
    2. ``LOGOS_CONFIG_DIR`` from ``environ`` / ``os.environ``.
    3. Walk parents from :func:`Path.cwd` looking for ``config/defaults.yaml``.
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
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"YAML root must be a mapping: {path}"
        raise ValueError(msg)
    return data


def load_merged_config_dict(
    config_dir: Path | str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Load ``defaults.yaml`` + ``local.yaml`` from *config_dir*, then env overrides."""
    root = resolve_config_dir(config_dir, environ=environ)
    defaults = load_yaml_dict(root / "defaults.yaml")
    local = load_yaml_dict(root / "local.yaml")
    merged = deep_merge(defaults, local)
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
    """Merge YAML + env and return :class:`~logos.ports.AppSettings`."""
    return merged_dict_to_app_settings(
        load_merged_config_dict(config_dir, environ=environ)
    )
