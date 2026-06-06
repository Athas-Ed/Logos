"""Paradigm router (PR): selects Agent execution paradigm per product Skill.

定案见 ``original_docs/重要子系统开发文档/范式路由与PR定案.md``：
``dialogue`` | ``react`` | ``plan`` | ``pipeline``（manifest 预绑定；远期可推断）。
"""

from __future__ import annotations

from typing import cast

from logos.agent.paradigm_types import Paradigm

_VALID: frozenset[str] = frozenset({"dialogue", "react", "plan", "pipeline"})


def select_paradigm(skill_id: str, *, user_text: str | None = None) -> Paradigm:
    """从产品 Skill manifest 读取 ``paradigm``（*user_text* 预留远期 ``paradigm_auto``）。"""
    from logos.platform.skills_registry import get_skill_manifest  # lazy: 避循环导入

    _ = user_text
    manifest = get_skill_manifest(skill_id)
    p = manifest.paradigm
    if p not in _VALID:
        msg = f"manifest paradigm invalid: {p!r} (skill_id={skill_id!r})"
        from logos.platform.skills_registry import SkillManifestNotFoundError  # lazy

        raise SkillManifestNotFoundError(msg)
    return cast(Paradigm, p)
