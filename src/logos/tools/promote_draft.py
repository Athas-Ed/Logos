"""草稿晋升 CLI 入口：`python -m logos.tools.promote_draft`（P1-A7-1 / P1-A7-2）。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from logos.tools.draft_promotion_fs import FilesystemDraftPromotionPort


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m logos.tools.promote_draft",
        description=(
            "将 workspace 下待晋升 Markdown 预览或复制至 KSFS，并在 --apply 后触发 HSI 同步。"
        ),
    )
    p.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="工作空间根目录（其下含草稿子目录，默认 setting_entry）",
    )
    p.add_argument(
        "--target-ksfs",
        required=True,
        type=Path,
        help="KSFS 根目录（paths.ksfs_root 语义）",
    )
    p.add_argument(
        "--drafts-relative",
        default="setting_entry",
        help="相对于 --workspace 的草稿根，默认 %(default)s（见 KSFS开发.md）",
    )
    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument(
        "--dry-run",
        action="store_true",
        help="只读：列出候选、mtime 与拟落户相对路径，不写盘",
    )
    mx.add_argument(
        "--apply",
        action="store_true",
        help="晋升当前扫描到的全部候选（单次事务；预检失败则不写盘）",
    )
    p.add_argument(
        "--hsi-db",
        type=Path,
        default=None,
        help="HSI SQLite 路径；默认 <当前工作目录>/.index/.high-speed_index",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="输出 INFO 级日志到 stderr",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(message)s",
            stream=sys.stderr,
        )

    workspace: Path = args.workspace.expanduser()
    ksfs: Path = args.target_ksfs.expanduser()
    drafts_root = (workspace / args.drafts_relative).resolve()
    ksfs_r = ksfs.resolve()
    hsi_db = (
        args.hsi_db.expanduser().resolve()
        if args.hsi_db is not None
        else (Path.cwd() / ".index" / ".high-speed_index").resolve()
    )

    if not workspace.is_dir():
        print(f"错误：--workspace 不是目录：{workspace}", file=sys.stderr)
        return 2

    port = FilesystemDraftPromotionPort(hsi_db=hsi_db)
    items = port.list_promotion_candidates(drafts_root, ksfs_r)

    print(f"草稿根: {drafts_root}")
    print(f"目标 KSFS 根: {ksfs_r}")
    print(f"HSI 库: {hsi_db}")
    print(f"候选数: {len(items)}")
    for it in items:
        print(
            f"  - 草稿: {it.draft_relpath!s}  mtime_ns={it.draft_mtime_ns}  "
            f"→  拟 KSFS: {it.proposed_ksfs_relpath!s}"
        )

    if args.dry_run:
        print("[dry-run] 未执行任何写盘操作。")
        return 0

    report = port.apply_promotion(drafts_root, ksfs_r, items)
    if report.ok:
        print(f"晋升成功，共 {len(report.applied)} 个文件：")
        for rel in report.applied:
            print(f"  + {rel}")
        return 0

    print(report.notes, file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
