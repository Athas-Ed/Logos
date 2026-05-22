"""``resources/pipelines/<profile>.yaml`` 阶段表解释。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .profile import pipelines_root

KNOWN_STEP_TYPES = frozenset(
    {
        "llm_json",
        "json_schema",
        "render",
        "overlap_scan",
        "promote_gate",
    }
)


@dataclass(frozen=True, slots=True)
class PipelineStepSpec:
    id: str
    type: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class PipelineSpec:
    profile_id: str
    steps: tuple[PipelineStepSpec, ...]


def load_pipeline_spec(profile_id: str) -> PipelineSpec:
    safe = profile_id.strip()
    path = pipelines_root() / f"{safe}.yaml"
    if not path.is_file():
        msg = f"pipeline spec not found: {profile_id!r}"
        raise FileNotFoundError(msg)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path}: pipeline spec must be a mapping"
        raise ValueError(msg)
    file_profile = raw.get("profile_id")
    if file_profile and str(file_profile).strip() != safe:
        msg = f"{path}: profile_id {file_profile!r} != filename {safe!r}"
        raise ValueError(msg)
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        msg = f"{path}: steps must be a non-empty list"
        raise ValueError(msg)
    steps: list[PipelineStepSpec] = []
    for i, item in enumerate(steps_raw):
        if not isinstance(item, dict):
            msg = f"{path}: steps[{i}] must be a mapping"
            raise ValueError(msg)
        step_id = item.get("id")
        step_type = item.get("type")
        if not isinstance(step_id, str) or not step_id.strip():
            msg = f"{path}: steps[{i}] missing id"
            raise ValueError(msg)
        if not isinstance(step_type, str) or step_type not in KNOWN_STEP_TYPES:
            msg = f"{path}: steps[{i}] unknown type: {step_type!r}"
            raise ValueError(msg)
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            msg = f"{path}: steps[{i}].enabled must be boolean"
            raise ValueError(msg)
        steps.append(
            PipelineStepSpec(
                id=step_id.strip(),
                type=step_type,
                enabled=enabled,
            )
        )
    return PipelineSpec(profile_id=safe, steps=tuple(steps))
