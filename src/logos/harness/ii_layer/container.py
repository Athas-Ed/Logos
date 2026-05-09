from __future__ import annotations

from dataclasses import dataclass

from logos.ports import (
    AppSettings,
    KnowledgeSource,
    LLMClient,
    MetadataIndex,
    RetrievalService,
    SemanticStore,
    TextEmbedder,
)


@dataclass(frozen=True, slots=True)
class AppPorts:
    """Composition root snapshot: all DIP ports available to HTTP handlers."""

    settings: AppSettings
    llm: LLMClient
    retrieval: RetrievalService
    knowledge_source: KnowledgeSource
    metadata_index: MetadataIndex
    semantic_store: SemanticStore
    text_embedder: TextEmbedder
