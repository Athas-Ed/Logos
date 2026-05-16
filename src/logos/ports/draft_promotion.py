"""草稿 → KSFS 晋升端口（`DraftPromotionPort`），与 `KSFS开发.md` §7.1 对齐。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PromotionItem:
    """单条可晋升草稿（相对路径相对各自根目录）。"""

    draft_relpath: str
    proposed_ksfs_relpath: str
    #: 在 ``list_promotion_candidates`` 时采集；``apply_promotion`` 须一致（KSFS §3.2）
    draft_mtime_ns: int


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """晋升执行结果摘要。"""

    applied: tuple[str, ...]
    skipped: tuple[str, ...]
    notes: str = ""
    ok: bool = True


@runtime_checkable
class DraftPromotionPort(Protocol):
    """CLI / GUI 共用的窄端口，避免业务逻辑双轨。"""

    def list_promotion_candidates(
        self, drafts_root: Path, ksfs_root: Path
    ) -> list[PromotionItem]:
        """列出 *drafts_root* 下可晋升的 Markdown 实体（不含各层 `README.md`）。"""

    def apply_promotion(
        self,
        drafts_root: Path,
        ksfs_root: Path,
        items: list[PromotionItem],
    ) -> PromotionReport:
        """将选中项晋升至 KSFS；须遵守 mtime 与禁止静默覆盖（见 `KSFS开发.md` §3.2、§7.3.1）。"""
