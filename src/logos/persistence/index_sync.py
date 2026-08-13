"""检索 seam 后的索引同步编排：``IndexSync`` 承诺 query 前"已索引"。

Candidate 2（架构深化）确立的约束：
- 检索侧（``FusedRetrievalService``）只依赖 ``logos.ports.retrieval.IndexSync`` 协议；
- 同步编排（HSI / SVS / Sparse 增量）全部藏在本模块之后，检索侧不得 import persistence；
- ``sync()``：每次全量对账（对应 ``sync_hsi_on_retrieve``）；
- ``sync_once()``：进程内至多一次 HSI 登记（原 ``registration.ensure_ksfs_hsi_registered`` 语义）。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from logos.ports.embedding import TextEmbedder
from logos.ports.sparse import SparseIndex
from logos.ports.vector import SemanticStore

from .hdl_sync import HdlSyncReport, sync_ksfs_hsi

_log = logging.getLogger("logos.persistence.index_sync")


class IndexSync:
    """查询前的索引同步编排（HSI 必做；SVS / Sparse 按装配启用）。

    构造参数语义（由组合根从 config 层翻译）：
    - ``sync_on_query=True``：``sync()`` 每次做全量增量对账；
    - ``sync_on_query=False``：``sync()`` 退化为进程内至多一次 HSI 登记（惰性兜底）；
    - ``sync_once()`` 始终为进程内至多一次 HSI 登记（startup 预热用）。
    """

    __slots__ = (
        "_ksfs_root",
        "_hsi_db",
        "_store",
        "_embedder",
        "_svs_state_db",
        "_sparse_index",
        "_sparse_db",
        "_sync_on_query",
        "_lock",
        "_once_done",
    )

    def __init__(
        self,
        *,
        ksfs_root: Path,
        hsi_db: Path,
        semantic_store: SemanticStore | None = None,
        embedder: TextEmbedder | None = None,
        svs_state_db: Path | None = None,
        sparse_index: SparseIndex | None = None,
        sparse_db: Path | None = None,
        sync_on_query: bool = True,
    ) -> None:
        self._ksfs_root = ksfs_root
        self._hsi_db = hsi_db
        self._store = semantic_store
        self._embedder = embedder
        self._svs_state_db = svs_state_db
        self._sparse_index = sparse_index
        self._sparse_db = sparse_db
        self._sync_on_query = sync_on_query
        self._lock = threading.Lock()
        self._once_done: set[str] = set()

    def _once_key(self) -> str:
        return f"{self._ksfs_root.resolve()}::{self._hsi_db.resolve()}"

    def sync_once(self) -> HdlSyncReport | None:
        """进程内至多一次 HSI 登记（幂等；原 ``ensure_ksfs_hsi_registered`` 语义）。"""
        key = self._once_key()
        with self._lock:
            if key in self._once_done:
                return None
            report = sync_ksfs_hsi(ksfs_root=self._ksfs_root, hsi_db=self._hsi_db)
            self._once_done.add(key)
            return report

    def sync(self) -> None:
        """query 前调用：承诺已装配的索引均与 KSFS 对账。"""
        if not self._sync_on_query:
            self.sync_once()
            return
        self._sync_all()

    def _sync_all(self) -> None:
        """全量增量对账：一次 HSI + 一次 KSFS 遍历，按装配分支双写 SVS / Sparse。"""
        from .chroma_bootstrap import sync_ksfs_indexes

        rep = sync_ksfs_indexes(
            ksfs_root=self._ksfs_root,
            hsi_db=self._hsi_db,
            semantic_store=self._store,
            embedder=self._embedder,
            svs_state_db=self._svs_state_db,
            sparse_index=self._sparse_index,
            sparse_db=self._sparse_db,
        )
        if (
            rep.svs_chunks_upserted > 0
            or rep.sparse_chunks_upserted > 0
            or rep.chunks_deleted_stale > 0
        ):
            _log.info(
                "检索前索引对账：扫描 %s 文档；SVS upsert %s 块；Sparse upsert %s 块；删块 %s",
                rep.hsi_documents_scanned,
                rep.svs_chunks_upserted,
                rep.sparse_chunks_upserted,
                rep.chunks_deleted_stale,
            )
        else:
            _log.debug(
                "检索前索引对账：扫描 %s 文档，无变更（SVS 跳过 %s，Sparse 跳过 %s）",
                rep.hsi_documents_scanned,
                rep.svs_documents_skipped_unchanged,
                rep.sparse_documents_skipped_unchanged,
            )
