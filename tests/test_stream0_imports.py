"""Stream 0：包导入烟测。"""

from __future__ import annotations


def test_import_logos_version() -> None:
    import logos

    assert logos.__version__ == "0.1.0"


def test_import_ports_symbols() -> None:
    from logos.ports import (
        AppSettings,
        ChatMessage,
        Citation,
        KnowledgeSource,
        LLMClient,
        MetadataIndex,
        MetadataRecord,
        RetrievalService,
        SemanticStore,
        SourceDocument,
        TextEmbedder,
        VectorQueryHit,
    )

    assert TextEmbedder.__name__ == "TextEmbedder"
    assert RetrievalService.__name__ == "RetrievalService"
    assert Citation.__name__ == "Citation"
    _ = (
        AppSettings,
        ChatMessage,
        KnowledgeSource,
        LLMClient,
        MetadataIndex,
        MetadataRecord,
        SemanticStore,
        SourceDocument,
        VectorQueryHit,
    )
