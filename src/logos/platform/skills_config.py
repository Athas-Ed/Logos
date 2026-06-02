"""技能运行时配置合并：manifest config_requirements 默认值 × deployment overrides。

约定：
- manifest 通过 ``config_requirements`` 声明该技能需要的配置键及其默认值。
- 部署者在 ``config/local.yaml → skills.overrides.<skill_id>`` 中覆盖这些值。
- 本模块提供唯一的合并入口，供技能执行代码消费。
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
    """合并 manifest config_requirements 默认值与 deployment overrides。

    Deployment overrides（``settings.skill_overrides[skill_id]``）优先级
    高于 manifest 默认值。

    返回的字典可直接传给技能执行逻辑（如工具参数、LLM 采样参数等）。

    若技能未声明 ``config_requirements``，返回空字典。
    """
    base = dict(manifest.config_requirements)
    overrides = settings.skill_overrides.get(skill_id, {})
    base.update(overrides)
    return base
