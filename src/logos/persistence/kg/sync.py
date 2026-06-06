"""从 KSFS 扫描 front matter relations[] 并同步到 CozoDB。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pycozo import Client

from . import normalize, open_db

# 跳过各层 README.md（它们不是实体）
_SKIP_PATTERNS = re.compile(r"(?:^|[/\\])README\.md$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class KGSyncReport:
    """单次同步摘要。"""

    entities_upserted: int
    relations_upserted: int
    stale_entities_removed: int
    stale_relations_removed: int
    files_scanned: int
    files_with_relations: int


def _scan_ksfs_md_files(ksfs_root: Path) -> list[Path]:
    """递归扫描 ksfs_root 下所有 .md 文件（排除 README.md）。"""
    result: list[Path] = []
    for f in sorted(ksfs_root.rglob("*.md")):
        if _SKIP_PATTERNS.search(str(f)):
            continue
        result.append(f)
    return result


def _parse_front_matter(text: str) -> dict[str, Any]:
    """解析 .md 文件的 YAML front matter（--- 之间的部分）。"""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def sync_kg_from_ksfs(
    ksfs_root: str | Path,
    db: Client | None = None,
    db_path: str | Path | None = None,
) -> KGSyncReport:
    """全量扫描 KSFS → 同步 CozoDB entity/relation 表。

    流程：
      1. 扫描所有 .md 文件（排除 README.md），解析 front matter
      2. 提取 slug/title/classification 写入 entity 表
      3. 提取 relations[] 写入 relation 表
      4. 删除不再存在的 entity 和 relation（全量对账）

    Args:
        ksfs_root: KSFS 根目录路径。
        db: 已打开的 CozoDB Client。为 ``None`` 时自动打开 ``db_path``。
        db_path: 仅当 ``db`` 为 ``None`` 时使用。
    """
    if db is None:
        db = open_db(db_path)

    root = Path(ksfs_root).resolve()
    md_files = _scan_ksfs_md_files(root)

    # ---- Phase 1: 收集当前 KSFS 的实体和关系 ----
    current_slugs: set[str] = set()
    entities: list[dict[str, str]] = []
    all_relations: list[dict[str, str]] = []
    files_with_rel = 0

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        fm = _parse_front_matter(text)
        slug = fm.get("slug") or md_path.stem
        current_slugs.add(slug)

        title = str(fm.get("title", "")) or slug
        classification = str(fm.get("classification", "unknown"))
        entities.append(
            {"slug": slug, "title": title, "classification": classification}
        )

        relations = fm.get("relations")
        # 兼容平铺格式：若 relations 为空字符串或 None，检查顶层 target_slug 字段
        if isinstance(relations, list):
            rel_list = relations
        elif isinstance(relations, str) and relations.strip():
            # YAML 列表可能被解析为字符串（极少见），尝试一次性构建
            rel_list = []
        else:
            rel_list = None

        if rel_list is not None:
            # relations[] 列表格式
            if rel_list:
                files_with_rel += 1
            for rel in rel_list:
                if not isinstance(rel, dict):
                    continue
                target = rel.get("target") or rel.get("target_slug")
                if not target:
                    continue
                all_relations.append(
                    {
                        "entity_slug": slug,
                        "type": str(rel.get("type", "related_to")),
                        "target_slug": str(target),
                    }
                )
        elif fm.get("target_slug"):
            # 平铺格式：顶层 target_slug / type / target_title / description
            files_with_rel += 1
            all_relations.append(
                {
                    "entity_slug": slug,
                    "type": str(fm.get("type", "related_to")),
                    "target_slug": str(fm["target_slug"]),
                }
            )

    # ---- Phase 2: 写入 CozoDB ----
    # entity 表：全量替换
    old_entity_slugs = set(
        row["slug"]
        for row in normalize(db.run('?[slug] := *entity{slug}'))
    )
    stale_entities = old_entity_slugs - current_slugs
    for stale_slug in stale_entities:
        # rm 需要所有列的值
        old = normalize(db.run(
            '?[title, classification] := *entity{slug: $slug, title, classification}',
            {"slug": stale_slug},
        ))
        if old:
            db.rm("entity", {
                "slug": stale_slug,
                "title": old[0]["title"],
                "classification": old[0]["classification"],
            })

    for ent in entities:
        db.put("entity", ent)

    # relation 表：全量替换
    old_relation_keys: set[tuple[str, str, str]] = set()
    for row in normalize(db.run(
        '?[entity_slug, type, target_slug] := *relation{entity_slug, type, target_slug}'
    )):
        old_relation_keys.add(
            (row["entity_slug"], row["type"], row["target_slug"])
        )

    new_relation_keys: set[tuple[str, str, str]] = set()
    for rel in all_relations:
        key = (rel["entity_slug"], rel["type"], rel["target_slug"])
        new_relation_keys.add(key)

    stale_relations = old_relation_keys - new_relation_keys
    for es, rt, ts in stale_relations:
        db.rm(
            "relation",
            {"entity_slug": es, "type": rt, "target_slug": ts},
        )

    for rel in all_relations:
        db.put("relation", rel)

    return KGSyncReport(
        entities_upserted=len(entities),
        relations_upserted=len(all_relations),
        stale_entities_removed=len(stale_entities),
        stale_relations_removed=len(stale_relations),
        files_scanned=len(md_files),
        files_with_relations=files_with_rel,
    )
