"""基于磁盘的 `DraftPromotionPort` 实现（P1-A7-2）：mtime 校验、禁止覆盖、复制后 HSI 同步。"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from logos.paths import PathSandboxViolationError, resolve_path_under_root
from logos.persistence.hdl_sync import sync_ksfs_hsi
from logos.ports.draft_promotion import PromotionItem, PromotionReport

log = logging.getLogger(__name__)


def _iter_markdown_entities(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        if p.name == "README.md":
            continue
        out.append(p)
    return out


class FilesystemDraftPromotionPort:
    """晋升至 ``ksfs_root`` 后调用 ``sync_ksfs_hsi`` 写 HSI（须传入可写 ``hsi_db``）。"""

    __slots__ = ("_hsi_db",)

    def __init__(self, *, hsi_db: Path) -> None:
        self._hsi_db = hsi_db

    def list_promotion_candidates(
        self, drafts_root: Path, ksfs_root: Path
    ) -> list[PromotionItem]:
        _ = ksfs_root
        root = drafts_root.resolve()
        items: list[PromotionItem] = []
        for path in _iter_markdown_entities(root):
            rel = path.relative_to(root).as_posix()
            try:
                resolve_path_under_root(root, rel)
            except PathSandboxViolationError:
                continue
            st = path.stat()
            items.append(
                PromotionItem(
                    draft_relpath=rel,
                    proposed_ksfs_relpath=rel,
                    draft_mtime_ns=st.st_mtime_ns,
                )
            )
        return items

    def apply_promotion(
        self,
        drafts_root: Path,
        ksfs_root: Path,
        items: list[PromotionItem],
    ) -> PromotionReport:
        drafts_r = drafts_root.resolve()
        ksfs_r = ksfs_root.resolve()
        if not items:
            return PromotionReport(applied=(), skipped=(), notes="未选择任何晋升项", ok=True)

        planned: list[tuple[PromotionItem, Path, Path]] = []
        errors: list[str] = []
        seen_dst: set[str] = set()

        for it in items:
            try:
                src = resolve_path_under_root(drafts_r, it.draft_relpath)
            except PathSandboxViolationError as exc:
                errors.append(f"草稿路径被拒绝：{it.draft_relpath!r} — {exc}")
                continue
            try:
                dst = resolve_path_under_root(ksfs_r, it.proposed_ksfs_relpath)
            except PathSandboxViolationError as exc:
                errors.append(f"KSFS 目标路径被拒绝：{it.proposed_ksfs_relpath!r} — {exc}")
                continue

            if not src.is_file():
                errors.append(f"草稿不存在或不是文件：{it.draft_relpath!r}")
                continue
            cur_mtime = src.stat().st_mtime_ns
            if cur_mtime != it.draft_mtime_ns:
                errors.append(
                    f"mtime 不一致，已中止：{it.draft_relpath!r} "
                    f"（记录 {it.draft_mtime_ns}，当前 {cur_mtime}）"
                )
                continue
            if dst.exists():
                errors.append(
                    f"目标已存在，拒绝静默覆盖（§7.3.1）：{it.proposed_ksfs_relpath!r}"
                )
                continue
            dst_key = Path(it.proposed_ksfs_relpath).as_posix()
            if dst_key in seen_dst:
                errors.append(f"重复的 KSFS 目标：{it.proposed_ksfs_relpath!r}")
                continue
            seen_dst.add(dst_key)
            planned.append((it, src, dst))

        if errors:
            msg = "; ".join(errors)
            log.warning("晋升预检失败：%s", msg)
            skipped = tuple(sorted({it.draft_relpath for it in items}))
            return PromotionReport(applied=(), skipped=skipped, notes=msg, ok=False)

        created: list[Path] = []
        applied_list: list[str] = []
        try:
            for _it, src, dst in planned:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                created.append(dst)
                applied_list.append(dst.relative_to(ksfs_r).as_posix())
                log.info("已晋升：%s -> %s", src, dst)
        except OSError as exc:
            for p in reversed(created):
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    log.exception("回滚删除失败：%s", p)
            msg = f"复制失败并已回滚：{exc}"
            log.error("%s", msg)
            skipped = tuple(sorted({it.draft_relpath for it, _, _ in planned}))
            return PromotionReport(
                applied=(), skipped=skipped, notes=msg, ok=False
            )

        try:
            report = sync_ksfs_hsi(ksfs_root=ksfs_r, hsi_db=self._hsi_db.resolve())
            log.info(
                "HSI 同步完成：scanned=%s upserted=%s",
                report.documents_scanned,
                report.hsi_upserted,
            )
        except OSError as exc:
            for p in reversed(created):
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    log.exception("HSI 失败后回滚删除失败：%s", p)
            msg = f"HSI 同步失败，已回滚 KSFS 新文件：{exc}"
            log.error("%s", msg)
            skipped = tuple(sorted({it.draft_relpath for it, _, _ in planned}))
            return PromotionReport(
                applied=(), skipped=skipped, notes=msg, ok=False
            )

        return PromotionReport(
            applied=tuple(applied_list),
            skipped=(),
            notes="",
            ok=True,
        )
