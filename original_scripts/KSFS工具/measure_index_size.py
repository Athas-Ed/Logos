"""
检测 KSFS 清理效果：对比 HSI / SVS 在同步前后的数据体量。

用法::

    # 只测量当前体量（删文件前确认基线）
    python scripts/KSFS工具/measure_index_size.py

    # 先触发 HSI+SVS 对账，再测量（删文件后清理索引）
    python scripts/KSFS工具/measure_index_size.py --sync

    # 仅 HSI（未装 chromadb 时）
    python scripts/KSFS工具/measure_index_size.py --sync --hsi-only

输出说明::

    [HSI]        .high-speed_index         935424  bytes  /  63  rows
    [SVS-state]  .svs_chunk_index.sqlite    40960  bytes  /  189  chunks
    [ChromaDB]   .vector_index/            1245184 bytes  /  1  collections
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from logos.platform.config.loader import load_app_settings


# ---------------------------------------------------------------------------
# 路径解析（与 sync_ksfs_now.py 一致）
# ---------------------------------------------------------------------------

def _resolve_repo_path(raw: str) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (_REPO_ROOT / p).resolve()


def _get_paths() -> dict[str, Path]:
    """返回各索引文件的绝对路径。AppSettings 使用扁平字段（非嵌套 paths.*）。"""
    settings = load_app_settings()

    hsi_db = _resolve_repo_path(settings.hsi_sqlite_path)

    # SVS 状态库：约定与 HSI 同目录，固定名 .svs_chunk_index.sqlite
    svs_state = hsi_db.parent / ".svs_chunk_index.sqlite"

    # Chroma 持久目录
    chroma_dir = _resolve_repo_path(settings.chroma_persist_directory)

    return {
        "hsi": hsi_db,
        "svs_state": svs_state,
        "chroma": chroma_dir,
    }


# ---------------------------------------------------------------------------
# 体量测量
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    """递归计算目录总字节数。"""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _count_hsi_rows(hsi_path: Path) -> int:
    """查询 HSI 表记录数。"""
    try:
        conn = sqlite3.connect(str(hsi_path))
        cur = conn.execute("SELECT COUNT(*) FROM hsi_metadata")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0
    except (sqlite3.Error, FileNotFoundError):
        return -1


def _count_svs_chunks(svs_path: Path) -> int:
    """查询 SVS 状态库的 chunk 记录数。"""
    try:
        conn = sqlite3.connect(str(svs_path))
        cur = conn.execute("SELECT COUNT(*) FROM svs_doc_embedding_state")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0
    except (sqlite3.Error, FileNotFoundError):
        return -1


def _count_chroma_collections(chroma_dir: Path) -> int:
    """粗略判断 ChromaDB 中有多少集合——查 Chroma 的 SQLite。"""
    # ChromaDB 在 persist_directory 下为每个 collection 建一个子目录
    # 每个子目录含 data_level0 等；直接数一级子目录个数  (排除 chroma.sqlite3)
    if not chroma_dir.is_dir():
        return -1
    count = 0
    for entry in chroma_dir.iterdir():
        if entry.is_dir():
            count += 1
    return count


def measure(paths: dict[str, Path]) -> dict:
    """返回各指标的当前值。"""
    hsi_path = paths["hsi"]
    svs_path = paths["svs_state"]
    chroma_path = paths["chroma"]

    return {
        "hsi_bytes": hsi_path.stat().st_size if hsi_path.is_file() else 0,
        "hsi_rows": _count_hsi_rows(hsi_path),
        "svs_state_bytes": svs_path.stat().st_size if svs_path.is_file() else 0,
        "svs_chunks": _count_svs_chunks(svs_path),
        "chroma_bytes": _dir_size(chroma_path) if chroma_path.is_dir() else 0,
        "chroma_collections": _count_chroma_collections(chroma_path),
    }


def format_report(label: str, m: dict) -> str:
    hsi_rows = str(m["hsi_rows"]) if m["hsi_rows"] >= 0 else "N/A"
    svs_chunks = str(m["svs_chunks"]) if m["svs_chunks"] >= 0 else "N/A"
    chroma_colls = str(m["chroma_collections"]) if m["chroma_collections"] >= 0 else "N/A"

    lines = [
        f"── {label} ──",
        f"  [HSI]        .high-speed_index          {m['hsi_bytes']:>10} bytes  /  {hsi_rows:>5} rows",
        f"  [SVS-state]  .svs_chunk_index.sqlite     {m['svs_state_bytes']:>10} bytes  /  {svs_chunks:>5} chunks",
        f"  [ChromaDB]   .vector_index/              {m['chroma_bytes']:>10} bytes  /  {chroma_colls:>3} collections",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 同步 HSI / SVS（复用 sync_ksfs_now.py 的逻辑）
# ---------------------------------------------------------------------------

def _do_sync_hsi(settings) -> object:
    """执行 HSI 对账，返回 HdlSyncReport。"""
    from logos.persistence import sync_ksfs_hsi

    ksfs_root = _resolve_repo_path(settings.ksfs_root)
    hsi_db = _resolve_repo_path(settings.hsi_sqlite_path)

    print(f"    扫描 KSFS: {ksfs_root}")
    print(f"    HSI 路径:  {hsi_db}")
    report = sync_ksfs_hsi(ksfs_root=ksfs_root, hsi_db=hsi_db)
    print(f"    → HSI 对账完成: "
          f"upsert={report.hsi_upserted}, "
          f"deleted_stale={report.hsi_deleted_stale}, "
          f"skipped={report.hsi_skipped_unchanged}")
    return report


def _do_sync_svs(settings):
    """执行 SVS 对账，返回 SvsSyncReport 或 None。"""
    from logos.persistence import sync_ksfs_svs_incremental
    from logos.persistence.chroma_bootstrap import default_svs_state_db_path

    try:
        from logos.infrastructure.vector.chroma_store import ChromaSemanticStore
    except ImportError:
        print("    未安装 chromadb，跳过 SVS 同步。", file=sys.stderr)
        return None

    ksfs_root = _resolve_repo_path(settings.ksfs_root)
    hsi_db = _resolve_repo_path(settings.hsi_sqlite_path)
    index_root = _resolve_repo_path(settings.index_root)
    svs_state = default_svs_state_db_path(index_root)

    store = ChromaSemanticStore(
        persist_directory=settings.chroma_persist_directory,
        collection_name=settings.chroma_collection,
    )

    try:
        from logos.infrastructure.embeddings.bge_small_zh import BgeSmallZhEmbedder
        model_dir = _resolve_repo_path(settings.embedding_model_path)
        embedder = BgeSmallZhEmbedder(str(model_dir))
    except ImportError:
        print("    未安装 sentence-transformers，跳过 SVS 同步。", file=sys.stderr)
        return None

    print(f"    扫描 KSFS: {ksfs_root}")
    print(f"    HSI 路径:  {hsi_db}")
    print(f"    SVS 状态:  {svs_state}")
    report = sync_ksfs_svs_incremental(
        ksfs_root=ksfs_root,
        hsi_db=hsi_db,
        store=store,
        embedder=embedder,
        svs_state_db=svs_state,
    )
    print(f"    → SVS 对账完成: "
          f"chunks_upserted={report.chunks_upserted}, "
          f"chunks_deleted_stale={report.chunks_deleted_stale}, "
          f"documents_skipped={report.documents_skipped_unchanged}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _delete_ksfs_paths(ksfs_root: Path, rel_paths: list[str]) -> int:
    """删除 ksfs_root 下的相对路径（文件/目录均支持），返回删除的文件数。"""
    import shutil

    total = 0
    for rel in rel_paths:
        target = (ksfs_root / rel).resolve()
        try:
            target.relative_to(ksfs_root.resolve())
        except ValueError:
            print(f"  跳过越界路径：{rel}", file=sys.stderr)
            continue
        if not target.exists():
            print(f"  路径不存在，跳过：{rel}")
            continue
        if target.is_dir():
            count = 0
            for f in target.rglob("*"):
                if f.is_file():
                    count += 1
            shutil.rmtree(target)
            print(f"  删除目录：{rel}（{count} 个文件）")
            total += count
        else:
            target.unlink()
            print(f"  删除文件：{rel}")
            total += 1
    return total


def main() -> None:
    ap = argparse.ArgumentParser(
        description="一键清理 KSFS 并验证 HSI/SVS 索引已跟进。\n"
        "默认：仅测量并报告当前索引体量。\n"
        "加 --clean 'Test/' 则：测前 → 删除路径 → HSI+SVS 对账 → 测后 → 对比报告。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--clean",
        nargs="+",
        metavar="REL_PATH",
        default=None,
        help="要删除的 KSFS 相对路径（可多个），如 --clean Test/ factions/ 。"
        "脚本会先测量、再删除、再同步索引、再测量对比。",
    )
    ap.add_argument(
        "--sync",
        action="store_true",
        help="仅执行 HSI+SVS 对账并再测，不删除文件。适合手动删文件后验证清理效果。",
    )
    ap.add_argument(
        "--hsi-only",
        action="store_true",
        help="仅同步 HSI（跳过 Chroma/SVS）。与 --clean 或 --sync 搭配使用。",
    )
    args = ap.parse_args()

    settings = load_app_settings()
    paths = _get_paths()
    ksfs_root = _resolve_repo_path(settings.ksfs_root)

    # ── 测前 ──
    before = measure(paths)
    print()
    print(format_report("清理前", before))
    print()

    # ── 删除（可选） ──
    deleted_files = 0
    if args.clean:
        print("── 删除 KSFS 文件 ──")
        deleted_files = _delete_ksfs_paths(ksfs_root, args.clean)
        print(f"  共删除 {deleted_files} 个文件")
        print()

    need_sync = deleted_files > 0 or args.sync

    # ── 同步（手动删文件后 --sync，或用 --clean 自动删） ──
    if need_sync:
        print("── 执行索引对账 ──")
        _do_sync_hsi(settings)
        if not args.hsi_only:
            _do_sync_svs(settings)
        print()

        # ── 测后 ──
        after = measure(paths)
        print(format_report("同步后", after))
        print()

        # ── 对比 ──
        delta_hsi = before["hsi_bytes"] - after["hsi_bytes"]
        delta_svs_state = before["svs_state_bytes"] - after["svs_state_bytes"]
        delta_chroma = before["chroma_bytes"] - after["chroma_bytes"]
        delta_rows = (before["hsi_rows"] - after["hsi_rows"]) if before["hsi_rows"] >= 0 and after["hsi_rows"] >= 0 else 0
        delta_chunks = (before["svs_chunks"] - after["svs_chunks"]) if before["svs_chunks"] >= 0 and after["svs_chunks"] >= 0 else 0

        print("── 变化量 ──")
        print(f"  HSI 数据库:     {before['hsi_bytes']:>10} → {after['hsi_bytes']:>10}  bytes  (减少 {delta_hsi:>10})")
        print(f"  HSI 记录数:     {before['hsi_rows']:>5} → {after['hsi_rows']:>5}  rows    (减少 {delta_rows:>5})")
        print(f"  SVS 状态库:     {before['svs_state_bytes']:>10} → {after['svs_state_bytes']:>10}  bytes  (减少 {delta_svs_state:>10})")
        print(f"  SVS chunk 数:   {before['svs_chunks']:>5} → {after['svs_chunks']:>5}  chunks  (减少 {delta_chunks:>5})")
        print(f"  ChromaDB 目录:  {before['chroma_bytes']:>10} → {after['chroma_bytes']:>10}  bytes  (减少 {delta_chroma:>10})")
        print()

        if delta_rows > 0 or delta_chunks > 0:
            print("✅ 旧数据已清除：索引体量明显下降。")
        elif before["hsi_rows"] == 0 and after["hsi_rows"] == 0:
            print("⚠️  HSI 前后均为空——可能 KSFS 已无实体文件。")
        else:
            if args.clean:
                print("ℹ️  体量无明显变化。可能原因：")
                print("   - 指定的 --clean 路径下没有实际实体 .md 文件")
                print("   - 索引文件大小不随 DELETE 立即收缩（看行数即可）")
            else:
                print("ℹ️  体量无明显变化。如果你还没有手动删除 KSFS 文件，")
                print("    这是正常的——先删文件，再跑 --sync 验证。")
        print()
    else:
        if args.clean:
            print("⚠️  未删除任何文件（路径不存在或已为空）。")
            print()
        print("── 常用用法 ──")
        print(f"  1. 测体量:              python scripts/KSFS工具/measure_index_size.py")
        print(f"  2. 手动删文件后验证:    python scripts/KSFS工具/measure_index_size.py --sync")
        print(f"  3. 自动清理并验证:      python scripts/KSFS工具/measure_index_size.py --clean Test/ factions/")
        print()


if __name__ == "__main__":
    main()
