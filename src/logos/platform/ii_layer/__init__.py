"""I&I HTTP surface: FastAPI factory, CORS, static GUI, FastAPI Depends for ports."""

from __future__ import annotations

__all__ = [
    "AppPorts",
    "AppPortsDep",
    "KnowledgeSourceDep",
    "LLMDep",
    "MetadataIndexDep",
    "RetrievalDep",
    "SemanticStoreDep",
    "SettingsDep",
    "TextEmbedderDep",
    "create_app",
    "default_gui_dist_dir",
    "get_app_ports",
    "get_knowledge_source",
    "get_llm",
    "get_metadata_index",
    "get_retrieval",
    "get_semantic_store",
    "get_settings",
    "get_text_embedder",
]


def __getattr__(name: str):
    if name == "AppPorts":
        from .container import AppPorts

        return AppPorts
    if name == "default_gui_dist_dir":
        from .paths import default_gui_dist_dir

        return default_gui_dist_dir
    if name == "create_app":
        from .app import create_app

        return create_app
    if name.startswith("get_") or name.endswith("Dep"):
        from . import deps as _deps

        return getattr(_deps, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
