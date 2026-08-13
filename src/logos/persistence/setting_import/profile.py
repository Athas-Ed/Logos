"""``resources/entity_template/<profile>/`` 加载。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from logos.platform.config.resolve import (
    entity_template_root as _resolved_entity_template_root,
)
from logos.platform.config.resolve import (
    pipelines_root as _resolved_pipelines_root,
)


@dataclass(frozen=True, slots=True)
class EntityTemplateProfile:
    profile_id: str
    root: Path
    schema_path: Path
    render_spec_path: Path
    llm_instructions_path: Path
    drafts_subdir: str


def entity_template_root() -> Path:
    return _resolved_entity_template_root()


def pipelines_root() -> Path:
    return _resolved_pipelines_root()


def load_entity_template_profile(profile_id: str) -> EntityTemplateProfile:
    safe = profile_id.strip()
    if not safe or safe != profile_id or "/" in safe or "\\" in safe or ".." in safe:
        msg = f"invalid entity template profile_id: {profile_id!r}"
        raise FileNotFoundError(msg)
    root = entity_template_root() / safe
    manifest_path = root / "manifest.yaml"
    if not manifest_path.is_file():
        msg = f"entity template profile not found: {profile_id!r}"
        raise FileNotFoundError(msg)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{manifest_path}: manifest must be a mapping"
        raise ValueError(msg)
    schema_name = str(raw.get("schema", "schema.json"))
    render_name = str(raw.get("render", "render_spec.yaml"))
    llm_name = str(raw.get("llm_instructions", "llm_instructions.md"))
    drafts_subdir = str(raw.get("drafts_subdir", "setting_entry")).strip() or "setting_entry"
    return EntityTemplateProfile(
        profile_id=safe,
        root=root,
        schema_path=root / schema_name,
        render_spec_path=root / render_name,
        llm_instructions_path=root / llm_name,
        drafts_subdir=drafts_subdir,
    )


def read_profile_text(path: Path) -> str:
    if not path.is_file():
        msg = f"missing profile resource: {path}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8")


def load_render_spec(profile: EntityTemplateProfile) -> dict[str, Any]:
    raw = yaml.safe_load(read_profile_text(profile.render_spec_path))
    if not isinstance(raw, dict):
        msg = f"{profile.render_spec_path}: render_spec must be a mapping"
        raise ValueError(msg)
    return raw
