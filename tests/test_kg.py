"""T-KG-01～05：KG 同步与查询测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logos.persistence.kg import open_db
from logos.persistence.kg.query import neighbors, shortest_path
from logos.persistence.kg.sync import sync_kg_from_ksfs


def _build_test_ksfs(tmp_path: Path, units: list[dict]) -> Path:
    """从 unit dicts 构建临时 KSFS 文件树。"""
    ksfs_root = tmp_path / "ksfs"
    ksfs_root.mkdir()
    for unit in units:
        slug = unit["slug"]
        cls = unit.get("classification", "character")
        title = unit.get("title", slug)
        relations = unit.get("relations", [])

        lines = ["---"]
        lines.append(f"slug: {slug}")
        lines.append(f"title: {title}")
        lines.append(f"classification: {cls}")
        if relations:
            lines.append("relations:")
            for r in relations:
                target = r.get("target_slug", "")
                rt = r.get("type", "related_to")
                lines.append(f"  - type: {rt}")
                lines.append(f"    target_slug: {target}")
        lines.append("---")
        (ksfs_root / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")
    return ksfs_root


def _clean_kg_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()


# ── 金样数据 ──
_CHAR_LIN = {
    "slug": "林冬",
    "title": "林冬",
    "classification": "character",
    "relations": [
        {"target_slug": "青阳镇", "type": "resides_in"},
    ],
}
_CHAR_MO = {
    "slug": "墨菲斯",
    "title": "墨菲斯·影刃",
    "classification": "character",
    "relations": [
        {"target_slug": "暗影议会", "type": "member_of"},
        {"target_slug": "夜幕匕首", "type": "owns"},
    ],
}
_LOC_QINGYANG = {
    "slug": "青阳镇",
    "title": "青阳镇",
    "classification": "location",
}
_FACTION_SHADOW = {
    "slug": "暗影议会",
    "title": "暗影议会",
    "classification": "faction",
}
_ITEM_DAGGER = {
    "slug": "夜幕匕首",
    "title": "夜幕匕首",
    "classification": "item",
    "relations": [
        {"target_slug": "墨菲斯", "type": "owned_by"},
    ],
}

_GOLDEN_UNITS = [_CHAR_LIN, _CHAR_MO, _LOC_QINGYANG, _FACTION_SHADOW, _ITEM_DAGGER]


# ═══════════════════════════════════════════════════════
# T-KG-01：单文件 relations 解析
# ═══════════════════════════════════════════════════════
def test_kg_01_single_file_relations(tmp_path: Path) -> None:
    """给定金样 .md → 边集合与 type/target_slug 一致。"""
    ksfs_root = _build_test_ksfs(tmp_path, [_CHAR_MO])
    db_path = tmp_path / ".index" / ".kg_cozo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_db(str(db_path))

    report = sync_kg_from_ksfs(ksfs_root, db=db)
    assert report.entities_upserted == 1
    assert report.relations_upserted == 2  # member_of + owns

    nbrs = neighbors(db, "墨菲斯")
    assert len(nbrs) == 2
    types_set = set()
    for n in nbrs:
        for t in n["types"]:
            types_set.add(t)
    assert "member_of" in types_set
    assert "owns" in types_set
    assert "暗影议会" in {n["slug"] for n in nbrs}
    assert "夜幕匕首" in {n["slug"] for n in nbrs}


# ═══════════════════════════════════════════════════════
# T-KG-02：多文件交叉引用
# ═══════════════════════════════════════════════════════
def test_kg_02_cross_references(tmp_path: Path) -> None:
    """多实体相互引用时，关系正确建立。"""
    ksfs_root = _build_test_ksfs(tmp_path, _GOLDEN_UNITS)
    db_path = tmp_path / ".index" / ".kg_cozo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_db(str(db_path))

    report = sync_kg_from_ksfs(ksfs_root, db=db)
    assert report.entities_upserted == 5
    assert report.relations_upserted == 4  # lin→青阳 + mo→议会 + mo→匕首 + dag→墨菲斯

    # 林冬 → 青阳镇
    nbrs = neighbors(db, "林冬")
    slugs = {n["slug"] for n in nbrs}
    assert "青阳镇" in slugs


# ═══════════════════════════════════════════════════════
# T-KG-03：删除实体后 sync 清除边
# ═══════════════════════════════════════════════════════
def test_kg_03_delete_entity_removes_edges(tmp_path: Path) -> None:
    """删除 KSFS 实体 → sync 后无该实体关联的边。"""
    ksfs_root = _build_test_ksfs(tmp_path, _GOLDEN_UNITS)
    db_path = tmp_path / ".index" / ".kg_cozo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_db(str(db_path))

    # 首次同步
    sync_kg_from_ksfs(ksfs_root, db=db)

    # 验证初始有边
    assert len(neighbors(db, "墨菲斯")) == 2

    # 删除墨菲斯的文件
    (ksfs_root / "墨菲斯.md").unlink()

    # 再次同步
    report = sync_kg_from_ksfs(ksfs_root, db=db)
    assert report.stale_entities_removed >= 1
    assert report.stale_relations_removed >= 2  # member_of + owns

    # 墨菲斯不应再出现在 KG 中
    nbrs = neighbors(db, "墨菲斯")
    assert len(nbrs) == 0


# ═══════════════════════════════════════════════════════
# T-KG-04：重命名 rel_path（slug 不变时无影响）
# ═══════════════════════════════════════════════════════
def test_kg_04_rename_file_same_slug(tmp_path: Path) -> None:
    """文件名变了但 front matter slug 不变 → 实体不变。"""
    ksfs_root = _build_test_ksfs(tmp_path, [_CHAR_LIN])
    db_path = tmp_path / ".index" / ".kg_cozo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_db(str(db_path))

    sync_kg_from_ksfs(ksfs_root, db=db)
    assert len(neighbors(db, "林冬")) == 1  # 有 resides_in 关系

    # 改名文件（slug 不变）
    (ksfs_root / "林冬.md").rename(ksfs_root / "renamed-lin.md")

    report = sync_kg_from_ksfs(ksfs_root, db=db)
    # 实体保持不变（slug 相同）
    assert report.stale_entities_removed == 0
    assert len(neighbors(db, "林冬")) == 1


# ═══════════════════════════════════════════════════════
# T-KG-05：邻居查询 + 最短路径
# ═══════════════════════════════════════════════════════
def test_kg_05_neighbors_and_shortest_path(tmp_path: Path) -> None:
    """多实体图中邻居查询和最短路径正确。"""
    ksfs_root = _build_test_ksfs(tmp_path, _GOLDEN_UNITS)
    db_path = tmp_path / ".index" / ".kg_cozo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_db(str(db_path))

    sync_kg_from_ksfs(ksfs_root, db=db)

    # 墨菲斯的邻居
    nbrs = neighbors(db, "墨菲斯")
    assert len(nbrs) == 2  # 暗影议会 + 夜幕匕首

    # 最短路径：墨菲斯 → 夜幕匕首（1跳）
    path = shortest_path(db, "墨菲斯", "夜幕匕首")
    assert path == ["墨菲斯", "夜幕匕首"]

    # 最短路径：林冬 → 暗影议会（无直接路径，不应返回）
    path = shortest_path(db, "林冬", "暗影议会")
    assert path is None  # 无连接

    # 两跳查询
    nbrs2 = neighbors(db, "墨菲斯", max_hops=2)
    slugs2 = {n["slug"] for n in nbrs2}
    assert "暗影议会" in slugs2
    assert "夜幕匕首" in slugs2
