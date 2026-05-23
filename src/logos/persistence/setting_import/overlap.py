"""设定导入：本地只读重叠扫描（F6-08；禁止 LLM 判定）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .profile import EntityTemplateProfile
from .render import load_render_spec


def unit_draft_rel_path(unit: dict[str, Any], *, render_spec: dict[str, Any]) -> str:
    """单元在 ``setting_entry/`` 根下的相对路径（不含 drafts_subdir 前缀）。"""
    classifications = render_spec.get("classifications") or {}
    class_key = unit["classification"]
    class_cfg = classifications.get(class_key)
    if not isinstance(class_cfg, dict):
        msg = f"render_spec missing classification: {class_key!r}"
        raise ValueError(msg)
    template = str(class_cfg.get("rel_path_template", ""))
    if not template:
        msg = f"empty rel_path_template for {class_key!r}"
        raise ValueError(msg)
    return template.format(slug=unit["slug"])


def scan_import_overlap(
    batch: dict[str, Any],
    *,
    profile: EntityTemplateProfile,
    workspace_root: Path | str,
    ksfs_root: Path | str,
) -> list[str]:
    """Schema 通过后扫描：批内重复 slug、草稿覆盖、KSFS 路径冲突。"""
    render_spec = load_render_spec(profile)
    ws = Path(workspace_root).resolve()
    ksfs = Path(ksfs_root).resolve()
    drafts_root = ws / profile.drafts_subdir

    warnings: list[str] = []
    seen_keys: dict[tuple[str, str], str] = {}

    for unit in batch.get("units") or []:
        if not isinstance(unit, dict):
            continue
        slug = str(unit.get("slug", "")).strip()
        classification = str(unit.get("classification", "")).strip()
        if not slug or not classification:
            continue
        key = (classification, slug)
        try:
            rel = unit_draft_rel_path(unit, render_spec=render_spec)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        if key in seen_keys:
            warnings.append(
                f"本批次重复：{classification}/{slug}（与 {seen_keys[key]} 相同）"
            )
        else:
            seen_keys[key] = rel

        draft_path = drafts_root / rel
        if draft_path.is_file():
            warnings.append(
                f"草稿路径已存在，渲染将覆盖：{profile.drafts_subdir}/{rel}"
            )

        ksfs_path = ksfs / rel
        if ksfs_path.is_file():
            warnings.append(
                f"KSFS 目标路径已存在，晋升将被拒绝：{rel}"
            )

    return warnings
