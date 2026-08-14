from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from logos.ports import AppSettings, McpServerEntry

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


def _coerce_truthy(raw: Any, *, default: bool = True) -> bool:
    """将 YAML / 环境变量中的真假值规范为 bool。"""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    s = str(raw).strip().lower()
    if s in ("0", "false", "no", "off", ""):
        return False
    if s in ("1", "true", "yes", "on"):
        return True
    return default


def _str_opt(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _parse_mcp_servers(skills: Mapping[str, Any]) -> tuple[McpServerEntry, ...]:
    raw = skills.get("mcp_servers")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        return ()
    out: list[McpServerEntry] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        sid = _str_opt(item.get("id"))
        if not sid:
            continue
        entrypoint = _str_opt(item.get("entrypoint"))
        if not entrypoint:
            continue
        env_raw = item.get("env") or {}
        env_pairs: list[tuple[str, str]] = []
        if isinstance(env_raw, Mapping):
            for k, v in env_raw.items():
                env_pairs.append((str(k), "" if v is None else str(v)))
        out.append(
            McpServerEntry(
                id=sid,
                # 已声明 id + entrypoint 即视为要挂载；省略 enabled 时默认开启，避免 silent skip
                enabled=_coerce_truthy(item.get("enabled"), default=True),
                entrypoint=entrypoint,
                strip_http_proxy=_coerce_truthy(
                    item.get("strip_http_proxy"), default=False
                ),
                env=frozenset(env_pairs),
            )
        )
    return tuple(out)


def _normalize_presentation(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("work", "developer"):
        return s
    return "work"


def _normalize_log_profile(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("minimal", "standard", "verbose", "audit"):
        return s
    return "standard"


def _coerce_non_negative_int(raw: Any, *, default: int) -> int:
    if raw is None:
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(0, n)


def _normalize_sse_max_num(raw: Any) -> int:
    n = _coerce_non_negative_int(raw, default=3)
    return max(1, n)


def _normalize_cache_warn_bytes(raw: Any) -> int:
    return _coerce_non_negative_int(raw, default=524288000)


def merged_dict_to_app_settings(data: Mapping[str, Any]) -> AppSettings:
    paths = data.get("paths") or {}
    emb = data.get("embeddings") or {}
    chroma = data.get("chroma") or {}
    llm = data.get("llm") or {}
    dev = data.get("developer") or {}
    skills = data.get("skills") or {}
    if isinstance(skills, Mapping):
        raw_mcp = skills.get("mcp_servers")
        if raw_mcp is not None and not isinstance(raw_mcp, list):
            msg = (
                "配置 skills.mcp_servers 必须为 YAML 列表（例如 `[]` 或 `- id: ...` 条目）。"
                f"当前类型为 {type(raw_mcp).__name__}。"
                "详见 original_docs/重要子系统开发文档/MCP开发.md。"
            )
            raise ValueError(msg)
    mcp_servers = _parse_mcp_servers(skills if isinstance(skills, Mapping) else {})
    overrides_raw = skills.get("overrides") if isinstance(skills, Mapping) else {}
    skill_overrides: dict[str, dict[str, Any]] = {}
    if isinstance(overrides_raw, dict):
        for k, v in overrides_raw.items():
            if isinstance(k, str) and isinstance(v, dict):
                skill_overrides[k] = dict(v)
    config_raw = skills.get("config") if isinstance(skills, Mapping) else {}
    skill_config_defaults: dict[str, Any] = {}
    if isinstance(config_raw, dict):
        skill_config_defaults = {str(k): v for k, v in config_raw.items()}
    ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
    obs = data.get("obs") if isinstance(data.get("obs"), dict) else {}
    agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
    react = agent.get("react") if isinstance(agent.get("react"), dict) else {}
    retrieval_raw = data.get("retrieval")
    retrieval = retrieval_raw if isinstance(retrieval_raw, dict) else {}
    sparse = retrieval.get("sparse") if isinstance(retrieval.get("sparse"), dict) else {}
    return AppSettings(
        workspace_root=str(paths.get("workspace_root", "./workspace")),
        example_ksfs_root=str(paths.get("example_ksfs_root", "./example_ksfs")),
        ksfs_root=str(paths.get("ksfs_root", "./resources/ksfs")),
        index_root=str(paths.get("index_root", "./.index")),
        logs_root=str(paths.get("logs_root", "./logs")),
        conversations_cache=str(
            paths.get("CONVERSATIONS_CACHE")
            or paths.get("conversations_cache")
            or "./workspace/conversations"
        ),
        hsi_sqlite_path=str(paths.get("hsi_sqlite_path", "./.index/.high-speed_index")),
        kg_db_path=str(paths.get("kg_db_path", "./.index/.kg_cozo.db")),
        writing_entry_subdir=str(
            paths.get("writing_entry_subdir", "writing_entry")
        ),
        pending_review_subdir=str(
            paths.get("pending_review_subdir", "pending_review")
        ),
        chroma_persist_directory=str(
            chroma.get("persist_directory", "./.index/.vector_index")
        ),
        chroma_collection=str(chroma.get("collection", "ksfs_chunks_v1")),
        embedding_provider=str(emb.get("provider", "bge_small_zh")),
        embedding_model_path=str(
            emb.get("model_path", "models/tooling/embeddings/bge-small-zh-v1.5")
        ),
        operating_mode=str(data.get("operating_mode", "author")),
        llm_api_key=str(llm.get("api_key", "") or ""),
        llm_base_url=str(llm.get("base_url", "https://api.deepseek.com/v1")),
        llm_model=str(llm.get("model", "deepseek-chat")),
        llm_provider=str(llm.get("provider", "") or ""),
        llm_max_tokens=max(1, _coerce_non_negative_int(llm.get("max_tokens"), default=4096)),
        llm_verify_ssl=_coerce_truthy(llm.get("verify_ssl"), default=True),
        llm_ca_bundle=_str_opt(llm.get("ca_bundle")),
        llm_http_proxy=_str_opt(llm.get("http_proxy")),
        llm_https_proxy=_str_opt(llm.get("https_proxy")),
        llm_no_proxy=_str_opt(llm.get("no_proxy")),
        ui_default_presentation=_normalize_presentation(ui.get("default_presentation")),
        ui_sse_max_num=_normalize_sse_max_num(
            ui.get("SSE_maxNum", ui.get("sse_max_num"))
        ),
        ui_cache_warn_bytes=_normalize_cache_warn_bytes(ui.get("cache_warn_bytes")),
        ui_max_history_full_text=max(1, _coerce_non_negative_int(ui.get("max_history_full_text"), default=5)),
        react_max_steps=max(1, _coerce_non_negative_int(react.get("max_steps"), default=16)),
        react_max_qa_steps=max(1, _coerce_non_negative_int(react.get("max_QA_steps"), default=20)),
        react_max_tool_observation_chars=_coerce_non_negative_int(
            react.get("max_tool_observation_chars"), default=100000
        ),
        obs_log_profile=_normalize_log_profile(obs.get("log_profile")),
        obs_show_log_root_in_gui=_coerce_truthy(
            obs.get("show_log_root_in_gui"), default=False
        ),
        developer_show_dev_tools_ui=_coerce_truthy(
            dev.get("show_dev_tools_ui"), default=False
        ),
        developer_prompt_echo=_coerce_truthy(dev.get("prompt_echo"), default=False),
        sync_hsi_on_startup=_coerce_truthy(
            paths.get("sync_hsi_on_startup"), default=False
        ),
        sync_hsi_on_retrieve=_coerce_truthy(
            paths.get("sync_hsi_on_retrieve"), default=True
        ),
        skill_overrides=skill_overrides,
        skill_config_defaults=skill_config_defaults,
        mcp_servers=mcp_servers,
        sparse_enabled=_coerce_truthy(sparse.get("enabled"), default=True),
        sparse_db_path=_str_opt(
            sparse.get("db_path", "./.index/.sparse_fts.sqlite")
        ),
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
