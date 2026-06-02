"""
渲染管线：将校验后的 JSON 批次按 ``render_spec.yaml`` 写为 ``workspace/setting_entry/`` 下的 Markdown 文件。

设计要点（求职 / 展示用）：
- YAML front matter 与正文分离：front matter 承载结构化元数据（tags / aliases / relations），
  供 HSI 索引和未来 KG 检索；正文供人阅读
- 配置驱动：分类→路径模板、front matter 白名单、章节顺序均由 render_spec.yaml 定义，
  不改代码即可新增实体类型
- relations 块序列渲染：实体间关系写入 YAML 头，格式为 YAML block sequence，
  确保被 HSI/Chroma 索引的同时保持人类可读
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from logos.persistence._paths import resolve_under_root

from .profile import EntityTemplateProfile, load_render_spec


@dataclass(frozen=True, slots=True)
class RenderedUnit:
    rel_path: str
    absolute_path: Path
    markdown: str


def _format_front_matter(fm: dict[str, Any]) -> str:
    lines: list[str] = ["---"]
    for key, value in fm.items():
        if value is None:
            continue
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            # YAML block sequence for dict items (relations, etc.)
            lines.append(f"{key}:")
            for item in value:
                lines.append("  -")
                for k, v in item.items():
                    lines.append(f"    {k}: {v}")
        elif isinstance(value, list):
            inner = ", ".join(str(v) for v in value)
            lines.append(f"{key}: [{inner}]")
        elif isinstance(value, str) and any(ch in value for ch in ('"', "\n", ":")):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def render_unit_markdown(
    batch: dict[str, Any],
    unit: dict[str, Any],
    *,
    render_spec: dict[str, Any],
) -> str:
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
    rel_path = template.format(slug=unit["slug"])

    allowlist = render_spec.get("front_matter_keys_allowlist") or []
    draft_id = render_spec.get("draft_id_placeholder", "待分配")
    fm: dict[str, Any] = {
        "id": draft_id,
        "title": unit.get("title") or unit["slug"],
        "tags": unit.get("tags") or [],
        "classification": class_key,
        "slug": unit["slug"],
        "batch_id": batch["batch_id"],
    }
    if batch.get("source_label"):
        fm["source_label"] = batch["source_label"]
    if unit.get("aliases"):
        fm["aliases"] = unit["aliases"]
    if unit.get("relations"):
        fm["relations"] = [
            {
                "target_slug": r["target_slug"],
                "type": r["type"],
            }
            for r in unit["relations"]
        ]
        for r, src in zip(fm["relations"], unit["relations"]):
            if src.get("target_title"):
                r["target_title"] = src["target_title"]
            if src.get("description"):
                r["description"] = src["description"]
    fm = {k: v for k, v in fm.items() if k in allowlist}

    parts: list[str] = [_format_front_matter(fm), ""]
    for section in render_spec.get("sections") or []:
        if not isinstance(section, dict):
            continue
        stype = section.get("type")
        if stype == "yaml_front_matter":
            continue
        if stype == "title_heading":
            heading_tpl = section.get("heading_template", "## {title}")
            title = unit.get("title") or unit["slug"]
            parts.append(heading_tpl.format(title=title, slug=unit["slug"]))
            parts.append("")
        elif stype == "body_markdown":
            parts.append(str(unit.get("body_markdown", "")).strip())
            parts.append("")
        elif stype == "relations_section":
            relations = unit.get("relations") or []
            if not relations:
                continue
            heading = str(section.get("heading", "## 关联实体"))
            parts.append(heading)
            parts.append("")
            line_tpl = str(section.get(
                "line_template",
                "- [{target_title}]({target_slug}) — {type}：{description}",
            ))
            line_fallback = str(section.get(
                "line_title_fallback_template",
                "- [{target_slug}]({target_slug}) — {type}：{description}",
            ))
            for rel in relations:
                if not isinstance(rel, dict):
                    continue
                ts = str(rel.get("target_slug", ""))
                tt = str(rel.get("target_title", "") or "")
                rtype = str(rel.get("type", ""))
                desc = str(rel.get("description", "") or "")
                if tt:
                    parts.append(line_tpl.format(
                        target_title=tt, target_slug=ts, type=rtype, description=desc,
                    ))
                else:
                    parts.append(line_fallback.format(
                        target_slug=ts, type=rtype, description=desc,
                    ))
            parts.append("")
        elif stype == "suggestions":
            suggestions = unit.get("suggestions") or []
            if not suggestions:
                continue
            parts.append(str(section.get("heading", "## 修改建议")))
            parts.append("")
            bullet_tpl = section.get(
                "bullet_template",
                "- （摘）「{verbatim_quote}」 — {message}",
            )
            bullet_no_quote = section.get("bullet_no_quote_template", "- {message}")
            for sug in suggestions:
                if not isinstance(sug, dict):
                    continue
                message = str(sug.get("message", "")).strip()
                quote = str(sug.get("verbatim_quote", "")).strip()
                if quote:
                    parts.append(
                        bullet_tpl.format(verbatim_quote=quote, message=message)
                    )
                else:
                    parts.append(bullet_no_quote.format(message=message))
            parts.append("")
    while parts and parts[-1] == "":
        parts.pop()
    return "\n".join(parts) + "\n"


def render_batch_to_setting_entry(
    batch: dict[str, Any],
    *,
    profile: EntityTemplateProfile,
    workspace_root: Path,
) -> list[RenderedUnit]:
    render_spec = load_render_spec(profile)
    drafts_root = workspace_root / profile.drafts_subdir
    drafts_root.mkdir(parents=True, exist_ok=True)
    written: list[RenderedUnit] = []
    for unit in batch.get("units") or []:
        if not isinstance(unit, dict):
            msg = "units[] must contain objects"
            raise ValueError(msg)
        markdown = render_unit_markdown(batch, unit, render_spec=render_spec)
        classifications = render_spec.get("classifications") or {}
        class_cfg = classifications[unit["classification"]]
        rel_path = str(class_cfg["rel_path_template"]).format(slug=unit["slug"])
        target = resolve_under_root(drafts_root, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8", newline="\n")
        written.append(
            RenderedUnit(
                rel_path=f"{profile.drafts_subdir}/{rel_path}",
                absolute_path=target,
                markdown=markdown,
            )
        )
    return written
