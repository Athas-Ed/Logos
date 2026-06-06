from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from .api_v1 import build_v1_router
from .container import AppPorts
from .paths import default_gui_dist_dir


@asynccontextmanager
async def _app_lifespan(app) -> AsyncIterator[None]:  # noqa: ANN001
    """可选：``paths.sync_hsi_on_startup`` 为真时在启动阶段登记 HSI（默认由检索懒登记）。"""
    ports: AppPorts = app.state.ports
    if ports.settings.sync_hsi_on_startup:
        from logos.persistence.registration import ensure_ksfs_hsi_registered

        ensure_ksfs_hsi_registered(
            ksfs_root=Path(ports.settings.ksfs_root).resolve(),
            hsi_db=Path(ports.settings.hsi_sqlite_path).resolve(),
        )
    yield


def create_app(
    ports: AppPorts,
    *,
    cors_allow_origins: Sequence[str] | None = None,
    static_dir: Path | None = None,
):
    """构建 FastAPI：CORS、``app.state.ports``、``/api/v1/*``、可选挂载 ``src/gui/dist`` 静态资源。"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
    except ImportError as e:
        raise ImportError(
            "使用 logos.platform.ii_layer.create_app 请先安装依赖：pip install fastapi"
        ) from e

    app = FastAPI(title="Logos I&I", lifespan=_app_lifespan)
    app.state.ports = ports

    origins = list(cors_allow_origins) if cors_allow_origins is not None else ["*"]
    allow_credentials = "*" not in origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(build_v1_router())

    root = static_dir if static_dir is not None else default_gui_dist_dir()
    if root.is_dir():
        app.mount("/", StaticFiles(directory=root, html=True), name="gui")

    return app


def main() -> None:
    """``python -m logos.platform.ii_layer.app`` 直接启动（供 Docker 入口使用）。"""
    import os
    import sys
    from pathlib import Path

    # 确保仓库根在 sys.path 上
    _repo = Path(__file__).resolve().parents[3]
    if str(_repo / "src") not in sys.path:
        sys.path.insert(0, str(_repo / "src"))

    os.chdir(_repo)
    os.environ.setdefault("LOGOS_REPO_ROOT", str(_repo))

    from logos.platform.config import load_app_settings
    from logos.platform.ii_layer.container import AppPorts
    from logos.platform.ii_layer.developer import DeveloperToggles
    from logos.platform.obs import configure_logging
    from logos.infrastructure.llm import build_chat_llm_from_settings
    from logos.infrastructure.retrieval.fused import FusedRetrievalService
    from logos.persistence import SqliteMetadataIndex
    from logos.persistence.ksfs_filesystem import FilesystemKnowledgeSource
    from logos.infrastructure.vector.chroma_store import ChromaSemanticStore
    from logos.infrastructure.embeddings.bge_small_zh import BgeSmallZhEmbedder

    settings = load_app_settings(config_dir=_repo / "config")
    configure_logging(settings)

    ksfs_root = Path(settings.ksfs_root).resolve()
    hsi_db = Path(settings.hsi_sqlite_path).resolve()
    index_root = Path(settings.index_root).resolve()
    metadata = SqliteMetadataIndex(hsi_db)

    # 尝试加载 Chroma + 嵌入（容器内可能无 GPU 加速，降级到桩也可运行）
    try:
        semantic_store = ChromaSemanticStore(
            persist_directory=settings.chroma_persist_directory,
            collection_name=settings.chroma_collection,
        )
    except Exception:  # noqa: BLE001
        semantic_store = _StubSemanticStore()

    try:
        embedder = BgeSmallZhEmbedder(str(Path(settings.embedding_model_path)))
    except Exception:  # noqa: BLE001
        embedder = _StubEmbedder512()

    from logos.persistence.chroma_bootstrap import default_svs_state_db_path
    svs_state_db = default_svs_state_db_path(index_root)

    retrieval = FusedRetrievalService(
        metadata_index=metadata,
        semantic_store=semantic_store,
        embedder=embedder,
        lazy_hsi_ksfs_root=ksfs_root,
        lazy_hsi_db_path=hsi_db,
        lazy_svs_state_db=svs_state_db if not isinstance(semantic_store, _StubSemanticStore) else None,
        refresh_indexes_on_query=settings.sync_hsi_on_retrieve,
    )
    knowledge_source = FilesystemKnowledgeSource(ksfs_root)

    llm = build_chat_llm_from_settings(settings) or _StubLLM()

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

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


class _StubLLM:
    """LLM 桩实现（无 API key 时使用）。"""
    def complete(self, messages, *, json_mode: bool = False) -> str:
        return "（Docker 桩后端）" + messages[-1].content

    def stream_completion(self, messages, *, json_mode: bool = False):
        text = self.complete(messages, json_mode=json_mode)
        step = 12
        for i in range(0, len(text), step):
            yield text[i : i + step]


class _StubSemanticStore:
    def upsert_chunks(self, **kwargs) -> None:
        return None
    def delete_ids(self, ids: list[str]) -> None:
        return None
    def query(self, query_embedding: list[float], top_k: int):
        return []


class _StubEmbedder512:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 512 for _ in texts]


if __name__ == "__main__":
    main()
