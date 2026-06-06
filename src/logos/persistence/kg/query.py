"""KG 查询函数：邻居、最短路径、子图扩展。

所有函数接受 ``db``（CozoDB Client）并在隔离事务中执行，不修改数据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pycozo import Client

from . import normalize, open_db


def neighbors(
    db: Client,
    slug: str,
    max_hops: int = 1,
    relation_type: str | None = None,
) -> list[dict[str, Any]]:
    """查询指定实体的邻居（关联实体）。

    Args:
        db: CozoDB Client。
        slug: 实体 slug（如 ``叶寒烟``）。
        max_hops: 扩展跳数（1 = 直接邻居，2 = 邻居的邻居）。
        relation_type: 可选，过滤关系类型（如 ``owns``）。

    Returns:
        ``[{slug, title, classification, type, hops}]``。
    """
    if max_hops == 1:
        return _neighbors_1hop(db, slug, relation_type)
    elif max_hops == 2:
        return _neighbors_2hop(db, slug, relation_type)
    else:
        return _neighbors_nhop(db, slug, max_hops, relation_type)


def _neighbors_1hop(
    db: Client, slug: str, rel_type: str | None = None,
) -> list[dict[str, Any]]:
    # 用 rtype 别名避免 type 保留字冲突
    if rel_type:
        rows = normalize(db.run(
            '?[target_slug, rtype] := *relation{entity_slug: $slug, type: $type, target_slug}',
            {"slug": slug, "type": rel_type},
        ))
    else:
        rows = normalize(db.run(
            '?[target_slug, rtype] := *relation{entity_slug: $slug, type: rtype, target_slug}',
            {"slug": slug},
        ))

    if not rows:
        return []

    slugs = [r["target_slug"] for r in rows]
    result_map: dict[str, dict[str, Any]] = {}

    # 获取实体信息
    for s in slugs:
        ent = normalize(db.run('?[title, classification] := *entity{slug: $slug, title, classification}', {"slug": s}))
        if ent:
            result_map[s] = {
                "slug": s,
                "title": ent[0]["title"],
                "classification": ent[0]["classification"],
                "types": [],
                "hops": 1,
            }
        else:
            result_map[s] = {
                "slug": s,
                "title": s,
                "classification": "unknown",
                "types": [],
                "hops": 1,
            }

    for r in rows:
        if r["target_slug"] in result_map:
            result_map[r["target_slug"]]["types"].append(r["rtype"])

    return list(result_map.values())


def _neighbors_2hop(
    db: Client, slug: str, rel_type: str | None = None,
) -> list[dict[str, Any]]:
    """两跳扩展：A → B → C 返回所有 B 和 C（去重）。"""
    # 一跳
    hop1 = _neighbors_1hop(db, slug, rel_type)
    hop1_slugs = {h["slug"] for h in hop1}

    # 二跳：从 hop1 实体继续扩展
    hop2: list[dict[str, Any]] = []
    seen: set[str] = set()
    for h in hop1:
        h2 = _neighbors_1hop(db, h["slug"], rel_type)
        for item in h2:
            if item["slug"] not in hop1_slugs and item["slug"] != slug and item["slug"] not in seen:
                item["hops"] = 2
                hop2.append(item)
                seen.add(item["slug"])

    return hop1 + hop2


def _neighbors_nhop(
    db: Client, slug: str, max_hops: int, rel_type: str | None = None,
) -> list[dict[str, Any]]:
    """N 跳扩展（递归）。"""
    all_results: list[dict[str, Any]] = []
    seen: set[str] = {slug}
    current_batch = [slug]

    for hop in range(1, max_hops + 1):
        next_batch: list[str] = []
        for s in current_batch:
            nbrs = _neighbors_1hop(db, s, rel_type)
            for n in nbrs:
                if n["slug"] not in seen:
                    n["hops"] = hop
                    all_results.append(n)
                    seen.add(n["slug"])
                    next_batch.append(n["slug"])
        current_batch = next_batch
        if not current_batch:
            break

    return all_results


def shortest_path(
    db: Client,
    from_slug: str,
    to_slug: str,
) -> list[str] | None:
    """查询两个实体之间的最短路径（BFS）。

    返回路径 slug 列表，如 ``[叶寒烟, 赤霄扇, 点苍茶棚]``。
    若不存在路径返回 ``None``。
    """
    if from_slug == to_slug:
        return [from_slug]

    visited: set[str] = {from_slug}
    queue: list[tuple[str, list[str]]] = [(from_slug, [from_slug])]

    while queue:
        current, path = queue.pop(0)
        nbrs = _neighbors_1hop(db, current)
        for n in nbrs:
            if n["slug"] == to_slug:
                return path + [n["slug"]]
            if n["slug"] not in visited:
                visited.add(n["slug"])
                queue.append((n["slug"], path + [n["slug"]]))

    return None


def expand_for_retrieval(
    db: Client,
    seed_slugs: list[str],
    max_hops: int = 1,
) -> list[dict[str, Any]]:
    """为检索做图扩展：从种子实体出发，返回关联实体列表。

    供 ``FusedRetrievalService`` 可选集成。
    """
    result: list[dict[str, Any]] = []
    seen: set[str] = set(seed_slugs)
    for seed in seed_slugs:
        nbrs = neighbors(db, seed, max_hops=max_hops)
        for n in nbrs:
            if n["slug"] not in seen:
                result.append(n)
                seen.add(n["slug"])
    return result
