"""V0.2 契约路由：大纲规划相关（保存、KSFS 条目查询）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from fastapi import HTTPException

from logos.paths import PathSandboxViolationError, resolve_path_under_root

from .deps import ResolvedPathsDep

_log = logging.getLogger("logos.api.outline")

_KSFS_LOOKUP_DIRS = {
    "role": frozenset({"人物", "角色", "characters", "cast"}),
    "location": frozenset({"地点", "场所", "locations", "places", "场景", "地区"}),
}


class SaveOutlineRequest(BaseModel):
    content: str
    filename: str | None = None


class SaveOutlineResponse(BaseModel):
    path: str


def build_outline_router() -> Any:
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/outlines/save")
    def save_outline(
        body: SaveOutlineRequest,
        paths: ResolvedPathsDep,
    ) -> SaveOutlineResponse:
        ws_root = paths.workspace_root
        outlines_dir = ws_root / "outlines"
        outlines_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = body.filename or f"outline_{ts}.md"
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        try:
            file_path = resolve_path_under_root(outlines_dir, safe_name)
        except PathSandboxViolationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        file_path.write_text(body.content, encoding="utf-8")
        rel = str(file_path.relative_to(ws_root))
        _log.info("大纲已保存: %s", rel)
        return SaveOutlineResponse(path=rel)

    @router.get("/ksfs/lookup")
    def list_ksfs_lookup(paths: ResolvedPathsDep) -> list[dict[str, str]]:
        ksfs_root = paths.ksfs_root
        entries: list[dict[str, str]] = []
        if not ksfs_root.is_dir():
            return entries
        for subdir in sorted(ksfs_root.iterdir()):
            if not subdir.is_dir():
                continue
            for lookup_type, dir_names in _KSFS_LOOKUP_DIRS.items():
                if subdir.name in dir_names:
                    for md_file in sorted(subdir.glob("*.md")):
                        entries.append({
                            "name": md_file.stem,
                            "path": str(md_file.relative_to(ksfs_root).as_posix()),
                            "type": lookup_type,
                        })
                    break
        return entries

    return router
