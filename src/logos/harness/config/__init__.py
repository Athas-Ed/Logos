"""Config: ``defaults.yaml`` + ``local.yaml`` merge and optional ``LOGOS_*`` env overrides."""

from logos.harness.config.loader import (
    apply_env_overrides,
    deep_merge,
    load_app_settings,
    load_merged_config_dict,
    load_yaml_dict,
    merged_dict_to_app_settings,
    resolve_config_dir,
)

__all__ = [
    "apply_env_overrides",
    "deep_merge",
    "load_app_settings",
    "load_merged_config_dict",
    "load_yaml_dict",
    "merged_dict_to_app_settings",
    "resolve_config_dir",
]
