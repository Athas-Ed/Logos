"""V0.1 内置工具参数 JSON Schema（与 :mod:`logos.harness.sg_layer.factory` 及 MCP Skill 同源）。"""

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
