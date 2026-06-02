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


def _create_tables(db: Client) -> None:
    """创建或确认 KG 三张表存在（幂等）。"""
    existing = {r["name"] for r in db.relations().to_dict("records")}
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
