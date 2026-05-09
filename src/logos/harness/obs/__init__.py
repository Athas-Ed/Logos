"""Obs: unified logging, ``logs/`` init, and structured formats for the ``logos`` namespace."""

from logos.harness.obs.logging_setup import (
    configure_logging,
    ensure_logs_directory,
    get_obs_logger,
)
from logos.harness.obs.structured_formatter import (
    JsonLineFormatter,
    log_record_to_payload,
    make_formatter,
)

__all__ = [
    "JsonLineFormatter",
    "configure_logging",
    "ensure_logs_directory",
    "get_obs_logger",
    "log_record_to_payload",
    "make_formatter",
]
