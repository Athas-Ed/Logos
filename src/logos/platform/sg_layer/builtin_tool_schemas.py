"""V0.1 内置工具参数 JSON Schema（与 :mod:`logos.platform.sg_layer.factory` 及 MCP Skill 同源）。"""

from __future__ import annotations

from typing import Any

JsonDict = dict[str, Any]

RETRIEVE_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "检索查询"},
        "top_k": {
            "type": "integer",
            "description": "返回条数上限，默认 8",
            "default": 8,
        },
    },
    "required": ["text"],
}

READ_KSFS_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "相对于 KSFS 根的路径，如 Test/note.md",
        },
    },
    "required": ["path"],
}

WRITE_DRAFT_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "相对于 workspace 根的路径，例如 notes/ch1.md",
        },
        "content": {"type": "string", "description": "文件完整文本"},
    },
    "required": ["path", "content"],
}


LIST_DRAFTS_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "相对于 workspace 根的路径，留空表示扫描全部非缓存草稿目录",
            "default": "",
        },
        "recursive": {
            "type": "boolean",
            "description": "是否递归遍历子目录",
            "default": True,
        },
        "max_entries": {
            "type": "integer",
            "description": "最多返回条数，默认 200，上限 1000",
            "default": 200,
        },
    },
    "required": [],
}


READ_DRAFT_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "相对于 workspace 根的草稿路径，例如 drafts/ch1.md",
        },
    },
    "required": ["path"],
}


PROMOTE_DRAFT_PARAMETERS: JsonDict = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "待晋升草稿的相对路径列表（相对于 workspace 根）",
        },
    },
    "required": ["items"],
}
