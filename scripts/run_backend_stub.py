"""本地开发：启动 FastAPI（`http://127.0.0.1:8000`）。

- 若在 ``config/local.yaml`` 中配置了 ``llm.api_key``（及可选 ``base_url`` / ``model``），
  则使用 **OpenAI 兼容** HTTP 客户端调用远程模型（如 DeepSeek）。
- 否则 LLM 为内存桩；检索与向量等仍为桩，便于先联调 GUI。

用法（仓库根、已激活 venv）::

    python scripts/run_backend_stub.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def main() -> None:
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit("请先安装开发依赖：pip install -e '.[dev]'") from e

    # 配置里的相对路径（如 ./workspace）以仓库根为基准，避免因从其它 cwd 启动而找不到目录。
    os.chdir(_REPO_ROOT)

    from logos.harness.config import load_app_settings
    from logos.harness.ii_layer.app import create_app
    from logos.harness.ii_layer.container import AppPorts
    from logos.infrastructure.llm import build_chat_llm_from_settings
    from logos.ports.knowledge_source import SourceDocument
    from logos.ports.retrieval import Citation

    class _StubLLM:
        def complete(self, messages, *, json_mode: bool = False) -> str:
            return "（桩后端）" + messages[-1].content

        def stream_completion(self, messages, *, json_mode: bool = False):
            text = self.complete(messages, json_mode=json_mode)
            step = 12
            for i in range(0, len(text), step):
                yield text[i : i + step]

    class _StubRetrieval:
        def query(self, *, text: str, top_k: int = 8):
            if "引用" in text:
                return [Citation(path="demo.md", snippet="示例片段", score=0.9)]
            return []

    class _StubKnowledgeSource:
        def iter_documents(self) -> list[SourceDocument]:
            return []

        def read_document(self, relative_path: str) -> SourceDocument:
            raise FileNotFoundError(relative_path)

    class _StubMetadataIndex:
        def upsert(self, records) -> None:  # noqa: ANN001
            return None

        def search_paths(self, *, prefix: str | None, limit: int):
            return []

    class _StubSemanticStore:
        def upsert_chunks(self, **kwargs) -> None:  # noqa: ANN003
            return None

        def delete_ids(self, ids: list[str]) -> None:
            return None

        def query(self, query_embedding: list[float], top_k: int):
            return []

    class _StubEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 8 for _ in texts]

    settings = load_app_settings(config_dir=_REPO_ROOT / "config")
    llm = build_chat_llm_from_settings(settings) or _StubLLM()
    ports = AppPorts(
        settings=settings,
        llm=llm,
        retrieval=_StubRetrieval(),
        knowledge_source=_StubKnowledgeSource(),
        metadata_index=_StubMetadataIndex(),
        semantic_store=_StubSemanticStore(),
        text_embedder=_StubEmbedder(),
    )
    app = create_app(ports)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
