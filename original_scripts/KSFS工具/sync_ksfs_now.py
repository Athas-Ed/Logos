"""立即对账 KSFS → HSI（及可选 SVS/Chroma），不依赖 retrieve。

删改 ``paths.ksfs_root`` 下实体 ``.md`` 后，在仓库根执行::

    python scripts/KSFS工具/sync_ksfs_now.py

仅更新 HSI（未装 chromadb / 嵌入模型时）::

    python scripts/KSFS工具/sync_ksfs_now.py --hsi-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from logos.persistence import (
    HdlSyncReport,
    SvsSyncReport,
    default_svs_state_db_path,
    sync_ksfs_hsi,
    sync_ksfs_svs_incremental,
)
from logos.platform.config.loader import load_app_settings


def _resolve_repo_path(raw: str) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (_REPO_ROOT / p).resolve()


def _try_svs_sync(
    *,
    ksfs_root: Path,
    hsi_db: Path,
    index_root: Path,
    settings: object,
) -> SvsSyncReport | None:
    from logos.ports import AppSettings

    s = settings
    assert isinstance(s, AppSettings)
    try:
        from logos.infrastructure.vector.chroma_store import ChromaSemanticStore
    except ImportError:
        print("未安装 chromadb，跳过 SVS/Chroma（仅 HSI 已同步）。", file=sys.stderr)
        return None

    store = ChromaSemanticStore(
        persist_directory=s.chroma_persist_directory,
        collection_name=s.chroma_collection,
    )
    embedder: object | None = None
    model_dir = Path(s.embedding_model_path)
    if not model_dir.is_absolute():
        model_dir = (_REPO_ROOT / model_dir).resolve()
    if model_dir.is_dir():
        try:
            from logos.infrastructure.embeddings.bge_small_zh import BgeSmallZhEmbedder

            embedder = BgeSmallZhEmbedder(str(model_dir))
        except ImportError:
            print(
                "未安装 sentence-transformers，无法做语义嵌入；"
                "请使用 --hsi-only 或安装依赖。",
                file=sys.stderr,
            )
            return None
    else:
        print(
            f"嵌入模型目录不存在：{model_dir}；跳过 SVS。",
            file=sys.stderr,
        )
        return None

    state_db = default_svs_state_db_path(index_root)
    return sync_ksfs_svs_incremental(
        ksfs_root=ksfs_root,
        hsi_db=hsi_db,
        store=store,
        embedder=embedder,
        svs_state_db=state_db,
    )


def _print_hsi(report: HdlSyncReport) -> None:
    print("--- HSI（sync_ksfs_hsi）---")
    print(f"  扫描文档数     : {report.documents_scanned}")
    print(f"  写入/更新行数  : {report.hsi_upserted}")
    print(f"  跳过未变       : {report.hsi_skipped_unchanged}")
    print(f"  删除陈旧路径   : {report.hsi_deleted_stale}")
    print(f"  新分配 id      : {report.hsi_ids_allocated}")
    print(f"  front matter 回写: {report.fm_id_writebacks}")
    if report.hsi_id_conflicts_resolved:
        print(f"  id 冲突重发号   : {report.hsi_id_conflicts_resolved}")


def _print_svs(report: SvsSyncReport) -> None:
    print("--- SVS（sync_ksfs_svs_incremental）---")
    print(f"  HSI 扫描文档数 : {report.hsi_documents_scanned}")
    print(f"  向量化文件数   : {report.documents_vectorized}")
    print(f"  跳过未变文件   : {report.documents_skipped_unchanged}")
    print(f"  upsert 块数    : {report.chunks_upserted}")
    print(f"  删除陈旧块数   : {report.chunks_deleted_stale}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="立即对账 KSFS → HSI/SVS（删除 .md 后清理索引用）",
    )
    p.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="配置目录（默认自动发现 config/）",
    )
    p.add_argument(
        "--hsi-only",
        action="store_true",
        help="仅 sync_ksfs_hsi，不更新 Chroma/SVS 状态库",
    )
    p.add_argument(
        "--ksfs-root",
        type=Path,
        default=None,
        help="覆盖 paths.ksfs_root",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_app_settings(args.config_dir)

    ksfs_root = (
        _resolve_repo_path(str(args.ksfs_root))
        if args.ksfs_root
        else _resolve_repo_path(settings.ksfs_root)
    )
    hsi_db = _resolve_repo_path(settings.hsi_sqlite_path)
    index_root = _resolve_repo_path(settings.index_root)

    if not ksfs_root.is_dir():
        print(f"KSFS 根不存在：{ksfs_root}", file=sys.stderr)
        return 1

    print(f"KSFS 根 : {ksfs_root}")
    print(f"HSI 库  : {hsi_db}")
    print(f"索引根  : {index_root}")

    hsi_report = sync_ksfs_hsi(ksfs_root=ksfs_root, hsi_db=hsi_db)
    _print_hsi(hsi_report)

    if args.hsi_only:
        print("\n（--hsi-only：未执行 SVS/Chroma 对账）")
        return 0

    svs_report = _try_svs_sync(
        ksfs_root=ksfs_root,
        hsi_db=hsi_db,
        index_root=index_root,
        settings=settings,
    )
    if svs_report is not None:
        _print_svs(svs_report)

    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(hsi_db)) as con:
        n = con.execute("SELECT COUNT(*) FROM hsi_metadata").fetchone()[0]
    print(f"\nHSI 当前实体行数: {n}")

    if hsi_report.hsi_deleted_stale == 0 and (
        svs_report is None or svs_report.chunks_deleted_stale == 0
    ):
        print(
            "提示：本轮无陈旧删除。若你刚删过 .md，请确认文件在 KSFS 扫描树下且非 README。",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
