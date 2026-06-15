from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class McpServerEntry:
    """声明式 MCP stdio 插件（相对仓库根的 ``entrypoint`` 脚本）。"""

    id: str
    enabled: bool
    entrypoint: str
    strip_http_proxy: bool = False
    env: frozenset[tuple[str, str]] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class AppSettings:
    """合并 defaults + local + 环境变量后的只读配置快照（Stream 1）。"""

    workspace_root: str
    example_ksfs_root: str
    ksfs_root: str  # KSFS 事实源；read_ksfs 仅允许读此树内相对路径
    index_root: str
    logs_root: str
    #: ``paths.CONVERSATIONS_CACHE``：档 B 会话 JSON 目录（相对仓库根或绝对路径）
    conversations_cache: str
    hsi_sqlite_path: str
    chroma_persist_directory: str
    chroma_collection: str
    embedding_provider: str
    embedding_model_path: str
    #: ``paths.writing_entry_subdir``：设定撰写草稿子目录（相对 workspace_root）
    writing_entry_subdir: str = "writing_entry"
    #: ``paths.pending_review_subdir``：审核晋升草稿子目录（相对 workspace_root）
    pending_review_subdir: str = "pending_review"
    operating_mode: str = "author"
    # LLM 提供商标识：openai / deepseek / anthropic / custom
    llm_provider: str = ""
    # OpenAI 兼容对话 API（DeepSeek、OpenAI 等）；api_key 为空则走桩实现
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # Anthropic 必填字段（对其他提供商无影响）
    llm_max_tokens: int = 4096
    # LLM HTTPS：校验与代理（由 config 合并 + LOGOS_LLM__* 覆盖）
    llm_verify_ssl: bool = True
    llm_ca_bundle: str = ""
    llm_http_proxy: str = ""
    llm_https_proxy: str = ""
    llm_no_proxy: str = ""
    #: ``ui.default_presentation``：work | developer
    ui_default_presentation: str = "work"
    #: ``ui.SSE_maxNum``：后台 SSE 并发上限（默认 3）
    ui_sse_max_num: int = 3
    #: ``ui.cache_warn_bytes``：会话缓存占用告警阈值（字节，默认 500 MiB）
    ui_cache_warn_bytes: int = 524288000
    #: ``ui.max_history_full_text``：连续问答 CB 保留最近几轮全文（默认 5）
    ui_max_history_full_text: int = 5
    #: ``agent.react.max_steps``：ReAct 范式默认步数上限（默认 16）
    react_max_steps: int = 16
    #: ``agent.react.max_QA_steps``：检索问答每轮 user 问题的步数上限（默认 20）
    react_max_qa_steps: int = 20
    #: ``obs.log_profile``：minimal | standard | verbose | audit
    obs_log_profile: str = "standard"
    #: ``obs.show_log_root_in_gui``：为 True 时 ``GET /api/v1/bootstrap`` 暴露 ``obs_logs_root``，供 GUI 展示日志根（Obs O4）；默认 False
    obs_show_log_root_in_gui: bool = False
    #: 为 true 时 GUI 可展示开发者控件并允许 PUT 切换 prompt 回显
    developer_show_dev_tools_ui: bool = False
    #: 启动初值；运行时可由 :class:`~logos.platform.ii_layer.developer.DeveloperToggles` 改写
    developer_prompt_echo: bool = False
    #: 进程启动时是否在 FastAPI lifespan 内执行一次 KSFS→HSI 登记（默认关闭）
    sync_hsi_on_startup: bool = False
    #: 每次 ``retrieve`` / 融合检索 ``query`` 前是否扫描 KSFS 并增量刷新 HSI/SVS（默认开启）
    sync_hsi_on_retrieve: bool = True
    #: ``paths.kg_db_path``（默认 "./.index/.kg_cozo.db"；被 factory.py 中 kg_query 工具消费）
    kg_db_path: str = "./.index/.kg_cozo.db"
    #: ``paths.setting_entry_subdir``：相对 ``pending_review_subdir`` 的草稿子目录（默认 "setting_entry"）
    setting_entry_subdir: str = "setting_entry"
    #: per-skill deployment overrides（config/local.yaml → skills.overrides.<skill_id>）
    skill_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: per-skill 调优参数全局默认值（config/defaults.yaml → skills.config），
    #  被 resolve_skill_config() 作为三层优先级的最底层
    skill_config_defaults: dict[str, Any] = field(default_factory=dict)
    #: MCP stdio 技能列表（``config`` 中 ``skills.mcp_servers``）；见 ``重要子系统开发文档/MCP开发.md``
    mcp_servers: tuple[McpServerEntry, ...] = field(default_factory=tuple)
