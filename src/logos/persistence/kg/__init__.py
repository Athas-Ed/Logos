"""知识图谱（KG）模块 — CozoDB + SQLite 后端。

数据流：KSFS .md front matter relations[] → CozoDB entity/relation 表 → Datalog 查询。

三张表：
  - entity: {slug: String, title: String, classification: String}
      节点：每个 KSFS 实体一条记录。
  - relation: {entity_slug: String, type: String, target_slug: String}
      边：front matter relations[] 每条一条记录。
  - entity_id: {slug: String, id: String}
      HSI id 映射：slug ↔ entity_id，用于与 HSI 交叉引用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pycozo import Client


def _default_db_path() -> Path:
    """返回默认 KG 数据库路径（与 HSI 同目录）。"""
    return Path(".index") / ".kg_cozo.db"


def normalize(result: dict[str, Any]) -> list[dict[str, Any]]:
    """将 pycozo 查询结果统一转为 ``list[dict]``。

    兼容两种返回格式：
      - 有 pandas：``DataFrame.to_dict("records")``
      - 无 pandas：``{'headers': [...], 'rows': [...]}``
    """
    if isinstance(result, dict) and "headers" in result and "rows" in result:
        headers = result["headers"]
        return [dict(zip(headers, row)) for row in result["rows"]]
    # 可能是 DataFrame 或已有 records 格式
    if hasattr(result, "to_dict"):
        return result.to_dict("records")  # type: ignore[union-attr]
    if isinstance(result, list):
        return result
    return []


def _create_tables(db: Client) -> None:
    """创建或确认 KG 三张表存在（幂等）。"""
    rels = db.relations()
    if isinstance(rels, dict):
        # pycozo 无 pandas 时返回 dict {'headers': [...], 'rows': [...]}
        existing = {row[0] for row in rels.get("rows", [])}
    else:
        # 有 pandas 时返回 DataFrame
        existing = {r["name"] for r in rels.to_dict("records")}
    for name, cols in [
        ("entity", ["slug", "title", "classification"]),
        ("relation", ["entity_slug", "type", "target_slug"]),
        ("entity_id", ["slug", "id"]),
    ]:
        if name not in existing:
            db.create(name, *cols)


def open_db(db_path: str | Path | None = None) -> Client:
    """打开（或创建）CozoDB SQLite 数据库，建表后返回 Client。

    Args:
        db_path: SQLite 文件路径。为 ``None`` 时使用 ``.index/.kg_cozo.db``。
    """
    path = str(db_path) if db_path is not None else str(_default_db_path())
    db = Client("sqlite", path)
    _create_tables(db)
    return db
