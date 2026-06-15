"""立即对账 KSFS → KG（CozoDB），不依赖检索。

在仓库根执行::

    python scripts/KSFS工具/sync_kg_now.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from logos.persistence.kg import open_db
from logos.persistence.kg.sync import sync_kg_from_ksfs


def main() -> None:
    ksfs_root = _REPO_ROOT / "resources" / "ksfs"
    db_path = _REPO_ROOT / ".index" / ".kg_cozo.db"

    print(f"KSFS 根: {ksfs_root}")
    print(f"KG 数据库: {db_path}")
    print()

    db = open_db(str(db_path))
    report = sync_kg_from_ksfs(ksfs_root, db=db)

    print(f"已扫描:   {report.files_scanned} 个 .md 文件")
    print(f"含关系:   {report.files_with_relations} 个文件")
    print(f"实体更新: {report.entities_upserted}")
    print(f"关系更新: {report.relations_upserted}")
    print(f"实体移除: {report.stale_entities_removed}")
    print(f"关系移除: {report.stale_relations_removed}")
    print()
    print("KG 同步完成。")


if __name__ == "__main__":
    main()
