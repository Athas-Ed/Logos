"""V0.2 契约路由：设定一致性检查（``POST /api/v1/setting-check``）。

前端直接调用（outline_plan 产出后自动触发，或 setting_check 独立使用），不走 Agent 工具。

权威文档：``original_docs/重要子系统开发文档/非必需可扩展/setting_check.md``。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from .deps import AppPortsDep, LLMDep, RetrievalDep

_log = logging.getLogger("logos.api.setting_check")


class SettingCheckItem(BaseModel):
    index: int
    content: str


class SettingCheckBody(BaseModel):
    items: list[SettingCheckItem] = Field(default_factory=list)


class SettingCheckConflict(BaseModel):
    item_index: int
    level: str
    ksfs_entry_path: str = ""
    description: str = ""


class SettingCheckResponse(BaseModel):
    conflicts: list[SettingCheckConflict] = Field(default_factory=list)


def build_setting_check_router() -> Any:
    from fastapi import APIRouter

    from logos.agent.setting_check import run_setting_check

    router = APIRouter()

    @router.post("/setting-check")
    def setting_check_v1(
        body: SettingCheckBody,
        llm: LLMDep,
        retrieval: RetrievalDep,
        ports: AppPortsDep,
    ) -> SettingCheckResponse:
        if not body.items:
            return SettingCheckResponse()
        result = run_setting_check(
            [{"index": it.index, "content": it.content} for it in body.items],
            retrieval=retrieval,
            llm=llm,
        )
        return SettingCheckResponse(
            conflicts=[
                SettingCheckConflict(
                    item_index=c.item_index,
                    level=c.level,
                    ksfs_entry_path=c.ksfs_entry_path,
                    description=c.description,
                )
                for c in result.conflicts
            ]
        )

    return router
