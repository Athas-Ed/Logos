from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppSettings:
    """合并 defaults + local + 环境变量后的只读配置快照（Stream 1）。"""

    workspace_root: str
    example_ksfs_root: str
    lkc_root: str  # LKC 根；read_lkc 仅允许读此树内相对路径
    index_root: str
    logs_root: str
    hsi_sqlite_path: str
    chroma_persist_directory: str
    chroma_collection: str
    embedding_provider: str
    embedding_model_path: str
    operating_mode: str = "author"
    # OpenAI 兼容对话 API（DeepSeek、OpenAI 等）；api_key 为空则走桩实现
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # LLM HTTPS：校验与代理（由 config 合并 + LOGOS_LLM__* 覆盖）
    llm_verify_ssl: bool = True
    llm_ca_bundle: str = ""
    llm_http_proxy: str = ""
    llm_https_proxy: str = ""
    llm_no_proxy: str = ""
    ui_default_presentation: str = "work"
    obs_log_profile: str = "standard"
