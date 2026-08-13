from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from logos.ports import (
    AppSettings,
    KnowledgeSource,
    LLMClient,
    MetadataIndex,
    RetrievalService,
    SemanticStore,
    TextEmbedder,
)

from .container import AppPorts
from logos.platform.config import ResolvedPaths, resolve_app_paths


def get_app_ports(request: Request) -> AppPorts:
    ports = getattr(request.app.state, "ports", None)
    if ports is None:
        raise RuntimeError(
            "应用未在 app.state 上配置 AppPorts，请先通过 create_app(ports=...) 注入。"
        )
    return ports


def get_settings(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> AppSettings:
    return ports.settings


def get_llm(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> LLMClient:
    return ports.llm


def get_retrieval(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> RetrievalService:
    return ports.retrieval


def get_knowledge_source(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> KnowledgeSource:
    return ports.knowledge_source


def get_metadata_index(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> MetadataIndex:
    return ports.metadata_index


def get_semantic_store(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> SemanticStore:
    return ports.semantic_store


def get_text_embedder(ports: Annotated[AppPorts, Depends(get_app_ports)]) -> TextEmbedder:
    return ports.text_embedder


def get_resolved_paths(
    ports: Annotated[AppPorts, Depends(get_app_ports)],
) -> ResolvedPaths:
    return resolve_app_paths(ports.settings)


AppPortsDep = Annotated[AppPorts, Depends(get_app_ports)]
SettingsDep = Annotated[AppSettings, Depends(get_settings)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
RetrievalDep = Annotated[RetrievalService, Depends(get_retrieval)]
KnowledgeSourceDep = Annotated[KnowledgeSource, Depends(get_knowledge_source)]
MetadataIndexDep = Annotated[MetadataIndex, Depends(get_metadata_index)]
SemanticStoreDep = Annotated[SemanticStore, Depends(get_semantic_store)]
TextEmbedderDep = Annotated[TextEmbedder, Depends(get_text_embedder)]
ResolvedPathsDep = Annotated[ResolvedPaths, Depends(get_resolved_paths)]
