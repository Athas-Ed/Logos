"""技能运行时配置合并：三层优先级链。

优先级（低→高）：
1. ``config/defaults.yaml → skills.config``（全局默认值）
2. ``skills/manifests/<id>.yaml → config_requirements``（技能出厂默认值）
3. ``config/local.yaml → skills.overrides.<skill_id>``（部署环境覆写）

所有消费端应通过 :func:`resolve_skill_config` 取值，而非直接读 manifest 字段。
"""

from __future__ import annotations

from typing import Any

from logos.ports.settings import AppSettings

from .skills_registry import SkillManifest


def resolve_skill_config(
    skill_id: str,
    manifest: SkillManifest,
    settings: AppSettings,
) -> dict[str, Any]:
    """合并三层配置，返回该技能的最终运行时参数字典。

    - 第 1 层：``settings.skill_config_defaults``（全局，对应 defaults.yaml skills.config）
    - 第 2 层：``manifest.config_requirements``（技能特化的出厂默认值）
    - 第 3 层：``settings.skill_overrides[skill_id]``（部署覆写，优先级最高）

    返回的字典可直接传给技能执行逻辑。
    """
    base = dict(settings.skill_config_defaults)
    base.update(manifest.config_requirements)
    overrides = settings.skill_overrides.get(skill_id, {})
    base.update(overrides)
    return base
