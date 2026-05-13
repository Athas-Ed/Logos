"""本地开发：启动 FastAPI（`http://127.0.0.1:8000`）。

- 若在 ``config/local.yaml`` 中配置了 ``llm.api_key``（及可选 ``base_url`` / ``model``），
  则使用 **OpenAI 兼容** HTTP 客户端调用远程模型（如 DeepSeek）。
- 否则 LLM 为内存桩。
- **检索**：从 ``paths.ksfs_root`` 同步 **HSI**（SQLite），并装配 ``FusedRetrievalService``。
  若已安装 ``chromadb`` 且 ``embeddings.model_path`` 下存在 BGE 权重，则启动时尝试 **重建 Chroma 单块索引**
  （每 Markdown 文件一块；失败则仅 HSI 关键词检索，并在日志中提示）。

用法（仓库根、已激活 venv）::

    python scripts/run_backend_stub.py

若 ``config`` 中 ``skills.mcp_servers`` 有 ``enabled: true`` 的项，请确认当前解释器已安装 ``mcp``（``pip install "mcp>=1.2.0"`` 或 ``pip install -e .``）；否则 MCP 无法挂载。
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

_log = logging.getLogger("logos.run_backend_stub")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit("请先安装开发依赖：pip install -e '.[dev]'") from e

    os.chdir(_REPO_ROOT)
    os.environ.setdefault("LOGOS_REPO_ROOT", str(_REPO_ROOT))

    from logos.harness.config import load_app_settings
    from logos.harness.ii_layer.app import create_app
    from logos.harness.ii_layer.container import AppPorts
    from logos.harness.ii_layer.developer import DeveloperToggles
    from logos.infrastructure.llm import build_chat_llm_from_settings
    from logos.infrastructure.retrieval.fused import FusedRetrievalService
    from logos.persistence import SqliteMetadataIndex, sync_ksfs_hsi
    from logos.persistence.chroma_bootstrap import reindex_ksfs_to_semantic_store
    from logos.persistence.ksfs_filesystem import FilesystemKnowledgeSource

    class _StubLLM:
        def complete(self, messages, *, json_mode: bool = False) -> str:
            return "（桩后端）" + messages[-1].content

        def stream_completion(self, messages, *, json_mode: bool = False):
            text = self.complete(messages, json_mode=json_mode)
            step = 12
            for i in range(0, len(text), step):
                yield text[i : i + step]

    class _StubSemanticStore:
        def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
            return None

        def delete_ids(self, ids: list[str]) -> None:
            return None

        def query(self, query_embedding: list[float], top_k: int):
            return []

    class _StubEmbedder512:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 512 for _ in texts]

    settings = load_app_settings(config_dir=_REPO_ROOT / "config")
    if any(s.enabled for s in settings.mcp_servers) and importlib.util.find_spec(
        "mcp"
    ) is None:
        print(
            "\n[Logos] 已启用至少一个 MCP 技能（skills.mcp_servers），但当前解释器未安装 Python 包 mcp。\n"
            f'  请执行: "{sys.executable}" -m pip install "mcp>=1.2.0"\n'
            "  或在仓库根: pip install -e .\n"
            "  安装后请重新启动本脚本。\n",
            file=sys.stderr,
        )
    llm = build_chat_llm_from_settings(settings) or _StubLLM()

    _log.info(
        "正在准备检索索引（KSFS→HSI，以及可选的 Chroma 重建）；"
        "此时尚未监听 http://127.0.0.1:8000 。"
        "若 Vite 已开，/api 代理可能出现 ECONNREFUSED，属正常，请待本进程打出 Uvicorn 启动日志后再刷新前端。"
    )

    ksfs_root = Path(settings.ksfs_root).resolve()
    hsi_db = Path(settings.hsi_sqlite_path).resolve()
    metadata = SqliteMetadataIndex(hsi_db)
    try:
        report = sync_ksfs_hsi(ksfs_root=ksfs_root, hsi_db=hsi_db)
        _log.info(
            "HSI 已同步：扫描 %s 条，写入 %s 条，跳过 %s 条",
            report.documents_scanned,
            report.hsi_upserted,
            report.hsi_skipped_unchanged,
        )
    except OSError:
        _log.exception("sync_ksfs_hsi 失败（检查 ksfs_root / 权限）")

    semantic_store = _StubSemanticStore()
    embedder: object = _StubEmbedder512()
    try:
        from logos.infrastructure.vector.chroma_store import ChromaSemanticStore

        semantic_store = ChromaSemanticStore(
            persist_directory=settings.chroma_persist_directory,
            collection_name=settings.chroma_collection,
        )
    except ImportError:
        _log.warning("未安装 chromadb，向量检索关闭（仅 HSI 关键词融合）")

    model_dir = Path(settings.embedding_model_path)
    if model_dir.is_dir():
        try:
            from logos.infrastructure.embeddings.bge_small_zh import BgeSmallZhEmbedder

            embedder = BgeSmallZhEmbedder(str(model_dir))
        except ImportError:
            _log.warning(
                "未安装 sentence-transformers，向量检索使用占位向量（效果差）"
            )

    if not isinstance(semantic_store, _StubSemanticStore):
        try:
            n = reindex_ksfs_to_semantic_store(
                ksfs_root=ksfs_root,
                store=semantic_store,
                embedder=embedder,
            )
            _log.info("Chroma 已写入 %s 个 KSFS 块（每文件一块）", n)
        except Exception:  # noqa: BLE001
            _log.exception("KSFS→Chroma 重建失败（仍可依赖 HSI 分支）")

    retrieval = FusedRetrievalService(
        metadata_index=metadata,
        semantic_store=semantic_store,
        embedder=embedder,
    )
    knowledge_source = FilesystemKnowledgeSource(ksfs_root)

    ports = AppPorts(
        settings=settings,
        llm=llm,
        retrieval=retrieval,
        knowledge_source=knowledge_source,
        metadata_index=metadata,
        semantic_store=semantic_store,
        text_embedder=embedder,
        developer=DeveloperToggles(prompt_echo=settings.developer_prompt_echo),
    )
    app = create_app(ports)
    _log.info("索引准备完毕，开始监听 http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
