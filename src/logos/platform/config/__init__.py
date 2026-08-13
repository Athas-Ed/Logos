"""配置：合并 ``defaults.yaml`` 与 ``local.yaml``，并支持 ``LOGOS_*`` 环境变量覆盖。"""

from logos.platform.config.loader import (
    apply_env_overrides,
    deep_merge,
    load_app_settings,
    load_merged_config_dict,
    load_yaml_dict,
    merged_dict_to_app_settings,
    resolve_config_dir,
)
from logos.platform.config.resolve import (
    ResolvedPaths,
    resolve_app_paths,
)

__all__ = [
    "apply_env_overrides",
    "deep_merge",
    "load_app_settings",
    "load_merged_config_dict",
    "load_yaml_dict",
    "merged_dict_to_app_settings",
    "resolve_config_dir",
    "ResolvedPaths",
    "resolve_app_paths",
]
