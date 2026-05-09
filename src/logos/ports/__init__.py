"""抽象端口（依赖倒置）。具体实现放在 infrastructure / persistence 等包中。"""

from logos.ports.embedding import TextEmbedder
from logos.ports.knowledge_source import KnowledgeSource, SourceDocument
from logos.ports.llm import ChatMessage, LLMClient
from logos.ports.metadata import MetadataIndex, MetadataRecord
from logos.ports.retrieval import Citation, RetrievalService
from logos.ports.settings import AppSettings
from logos.ports.vector import SemanticStore, VectorQueryHit

__all__ = [
    "AppSettings",
    "ChatMessage",
    "Citation",
    "KnowledgeSource",
    "LLMClient",
    "MetadataIndex",
    "MetadataRecord",
    "RetrievalService",
    "SemanticStore",
    "SourceDocument",
    "TextEmbedder",
    "VectorQueryHit",
]
