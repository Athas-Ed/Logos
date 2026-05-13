"""Process-wide one-shot KSFS→HSI registration (KSFS §3.2 / §3.3)."""

from __future__ import annotations

import threading
from pathlib import Path

from .hdl_sync import HdlSyncReport, sync_ksfs_hsi

_lock = threading.Lock()
_done: set[str] = set()


def ensure_ksfs_hsi_registered(*, ksfs_root: Path, hsi_db: Path) -> HdlSyncReport | None:
    """Run ``sync_ksfs_hsi`` at most once per process for a given root/db pair."""
    key = f"{ksfs_root.resolve()}::{hsi_db.resolve()}"
    with _lock:
        if key in _done:
            return None
        report = sync_ksfs_hsi(ksfs_root=ksfs_root, hsi_db=hsi_db)
        _done.add(key)
        return report
