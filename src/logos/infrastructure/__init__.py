"""基础设施（检索、模型侧、工具调用适配等）— Stream 3。

子模块（如 ``llm``）导入时**不**再强行加载 Chroma / BGE，避免仅启动 HTTP+LLM 时拖入重型依赖或触发副作用。
"""

from __future__ import annotations

__all__ = [
    "BgeSmallZhEmbedder",
    "ChromaSemanticStore",
    "FusedRetrievalService",
]


def __getattr__(name: str):
    if name == "BgeSmallZhEmbedder":
        from logos.infrastructure.embeddings import BgeSmallZhEmbedder

        return BgeSmallZhEmbedder
    if name == "ChromaSemanticStore":
        from logos.infrastructure.vector import ChromaSemanticStore

        return ChromaSemanticStore
    if name == "FusedRetrievalService":
        from logos.infrastructure.retrieval import FusedRetrievalService

        return FusedRetrievalService
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
