"""产品 Skill manifest 注册表（F5-01）。

物理路径写死为 ``<repo>/skills/manifests/<skill_id>.yaml``（与 MCP 工具包 ``skills/<包>/`` 并列，勿混称）。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from logos.agent.paradigm_types import Paradigm
from logos.platform.mcp_stdio import resolve_repo_root

PersistenceTier = Literal["p0", "p1", "p2"]
TurnPolicy = Literal["single", "multi"]

_REQUIRED_FIELDS = (
    "skill_id",
    "display_name",
    "persistence_tier",
    "paradigm",
    "turn_policy",
    "allowed_tools",
    "prompt_runtime_key",
    "input_schema",
)

_VALID_TIERS = frozenset({"p0", "p1", "p2"})
_VALID_PARADIGMS = frozenset({"dialogue", "react", "plan", "pipeline"})
_VALID_TURN = frozenset({"single", "multi"})


class SkillManifestError(ValueError):
    """manifest 解析或校验失败。"""


class SkillManifestNotFoundError(SkillManifestError):
    """未知 ``skill_id``。"""


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """产品 Skill manifest（逻辑模型，见 Skill形态与Prompt工程.md §6）。"""

    skill_id: str
    display_name: str
    persistence_tier: PersistenceTier
    paradigm: Paradigm
    turn_policy: TurnPolicy
    allowed_tools: tuple[str, ...]
    prompt_runtime_key: str
    input_schema: dict[str, Any]
    description: str = ""
    #: GUI「技能说明」区块正文（任务页 / 对话页按 skill_id 注入）
    ui_instructions: str = ""
    blueprint_path: str | None = None
    #: ``paradigm: pipeline`` 时必填；指向 ``resources/pipelines/<name>.yaml`` 与 entity_template profile
    pipeline_profile: str | None = None


def manifests_dir() -> Path:
    """``skills/manifests`` 目录（相对仓库根）。"""
    return resolve_repo_root() / "skills" / "manifests"


def _manifest_path(skill_id: str) -> Path:
    safe = skill_id.strip()
    if not safe or safe != skill_id or "/" in safe or "\\" in safe or ".." in safe:
        raise SkillManifestNotFoundError(f"invalid skill_id: {skill_id!r}")
    return manifests_dir() / f"{safe}.yaml"


def _parse_manifest_file(path: Path, *, expected_id: str) -> SkillManifest:
    if not path.is_file():
        raise SkillManifestNotFoundError(f"skill manifest not found: {expected_id!r}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SkillManifestError(f"{path}: manifest must be a YAML mapping")
    return _validate_manifest_dict(raw, source=str(path))


def _validate_manifest_dict(raw: dict[str, Any], *, source: str) -> SkillManifest:
    missing = [k for k in _REQUIRED_FIELDS if k not in raw]
    if missing:
        raise SkillManifestError(f"{source}: missing required fields: {', '.join(missing)}")

    skill_id = raw["skill_id"]
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise SkillManifestError(f"{source}: skill_id must be a non-empty string")

    tier = raw["persistence_tier"]
    if tier not in _VALID_TIERS:
        raise SkillManifestError(f"{source}: invalid persistence_tier: {tier!r}")

    paradigm = raw["paradigm"]
    if paradigm not in _VALID_PARADIGMS:
        raise SkillManifestError(f"{source}: invalid paradigm: {paradigm!r}")

    turn_policy = raw["turn_policy"]
    if turn_policy not in _VALID_TURN:
        raise SkillManifestError(f"{source}: invalid turn_policy: {turn_policy!r}")

    allowed = raw["allowed_tools"]
    if not isinstance(allowed, list) or not all(isinstance(t, str) for t in allowed):
        raise SkillManifestError(f"{source}: allowed_tools must be a list of strings")

    input_schema = raw["input_schema"]
    if not isinstance(input_schema, dict):
        raise SkillManifestError(f"{source}: input_schema must be a mapping")

    display_name = raw["display_name"]
    if not isinstance(display_name, str) or not display_name.strip():
        raise SkillManifestError(f"{source}: display_name must be a non-empty string")

    prompt_runtime_key = raw["prompt_runtime_key"]
    if not isinstance(prompt_runtime_key, str) or not prompt_runtime_key.strip():
        raise SkillManifestError(f"{source}: prompt_runtime_key must be a non-empty string")

    description = raw.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise SkillManifestError(f"{source}: description must be a string")

    ui_instructions = raw.get("ui_instructions", "")
    if ui_instructions is None:
        ui_instructions = ""
    if not isinstance(ui_instructions, str):
        raise SkillManifestError(f"{source}: ui_instructions must be a string")

    blueprint_path = raw.get("blueprint_path")
    if blueprint_path is not None and not isinstance(blueprint_path, str):
        raise SkillManifestError(f"{source}: blueprint_path must be a string")

    pipeline_profile_raw = raw.get("pipeline_profile")
    if paradigm == "pipeline":
        if not isinstance(pipeline_profile_raw, str) or not pipeline_profile_raw.strip():
            raise SkillManifestError(
                f"{source}: pipeline_profile required when paradigm is pipeline"
            )
        pipeline_profile = pipeline_profile_raw.strip()
    else:
        if pipeline_profile_raw is not None:
            raise SkillManifestError(
                f"{source}: pipeline_profile only allowed when paradigm is pipeline"
            )
        pipeline_profile = None

    return SkillManifest(
        skill_id=skill_id,
        display_name=display_name,
        persistence_tier=tier,
        paradigm=paradigm,
        turn_policy=turn_policy,
        allowed_tools=tuple(allowed),
        prompt_runtime_key=prompt_runtime_key,
        input_schema=dict(input_schema),
        description=description,
        ui_instructions=ui_instructions.strip(),
        blueprint_path=blueprint_path,
        pipeline_profile=pipeline_profile,
    )


@lru_cache(maxsize=64)
def get_skill_manifest(skill_id: str) -> SkillManifest:
    """按 ``skill_id`` 加载并校验产品 Skill manifest；未知 id 抛 ``SkillManifestNotFoundError``。"""
    path = _manifest_path(skill_id)
    manifest = _parse_manifest_file(path, expected_id=skill_id)
    if manifest.skill_id != skill_id:
        raise SkillManifestError(
            f"{path}: skill_id field {manifest.skill_id!r} does not match filename {skill_id!r}"
        )
    return manifest


def list_builtin_skill_ids() -> tuple[str, ...]:
    """返回 ``skills/manifests/*.yaml`` 中的全部 ``skill_id``（按文件名排序）。"""
    root = manifests_dir()
    if not root.is_dir():
        return ()
    ids: list[str] = []
    for p in sorted(root.glob("*.yaml")):
        stem = p.stem
        if stem and stem == p.name[:-5]:
            ids.append(stem)
    return tuple(ids)


@dataclass(frozen=True, slots=True)
class BootstrapSkillSummary:
    """``GET /api/v1/bootstrap`` 的 ``skills[]`` 项（F5-08）。"""

    skill_id: str
    display_name: str
    description: str
    ui_instructions: str
    persistence_tier: PersistenceTier
    paradigm: Paradigm


def list_bootstrap_skill_summaries() -> tuple[BootstrapSkillSummary, ...]:
    """供技能面板渲染的产品 Skill 摘要列表（全部 manifest）。"""
    summaries: list[BootstrapSkillSummary] = []
    for skill_id in list_builtin_skill_ids():
        manifest = get_skill_manifest(skill_id)
        summaries.append(
            BootstrapSkillSummary(
                skill_id=manifest.skill_id,
                display_name=manifest.display_name,
                description=manifest.description,
                ui_instructions=manifest.ui_instructions,
                persistence_tier=manifest.persistence_tier,
                paradigm=manifest.paradigm,
            )
        )
    return tuple(summaries)
