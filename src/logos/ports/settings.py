from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppSettings:
    """合并 defaults + local + 环境变量后的只读配置快照（Stream 1）。"""

    workspace_root: str
    example_ksfs_root: str
    ksfs_root: str  # KSFS 事实源；read_ksfs 仅允许读此树内相对路径
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
    #: 为 true 时 GUI 可展示开发者控件并允许 PUT 切换 prompt 回显
    developer_show_dev_tools_ui: bool = False
    #: 启动初值；运行时可由 :class:`~logos.harness.ii_layer.developer.DeveloperToggles` 改写
    developer_prompt_echo: bool = False
    #: 高德天气 MCP（``skills/amap-weather-mcp``）；密钥走 ``skills.amap_weather.web_api_key`` 或环境变量
    skills_amap_weather_enabled: bool = False
    skills_amap_weather_web_api_key: str = ""
