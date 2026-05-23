"""观测（Obs）：统一日志、``logs/`` 目录初始化，以及 ``logos`` 命名空间下的结构化格式。"""

from logos.platform.obs.logging_setup import (
    configure_logging,
    ensure_logs_directory,
    get_obs_logger,
)
from logos.platform.obs.structured_formatter import (
    JsonLineFormatter,
    log_record_to_payload,
    make_formatter,
)
from logos.platform.obs.tool_chain import (
    TOOL_CHAIN_EVENT_V1,
    classify_tool_observation,
    clear_obs_log_profile_tls,
    current_obs_profile,
    emit_tool_chain_v1,
    param_digest_for_log,
    prime_obs_log_profile_for_chat,
    reset_react_tool_steps,
)

__all__ = [
    "JsonLineFormatter",
    "TOOL_CHAIN_EVENT_V1",
    "classify_tool_observation",
    "clear_obs_log_profile_tls",
    "configure_logging",
    "current_obs_profile",
    "emit_tool_chain_v1",
    "ensure_logs_directory",
    "get_obs_logger",
    "log_record_to_payload",
    "make_formatter",
    "param_digest_for_log",
    "prime_obs_log_profile_for_chat",
    "reset_react_tool_steps",
]
