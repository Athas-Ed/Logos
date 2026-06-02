"""V0.2 契约路由：开发者工具（``GET /api/v1/developer/*``）。

权威文档：``original_docs/重要子系统开发文档/API-V0.2.md``。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from .deps import AppPortsDep, RetrievalDep

_log = logging.getLogger("logos.api.developer")


class DeveloperUIResponse(BaseModel):
    show_dev_tools_ui: bool
    prompt_echo: bool


class PromptEchoBody(BaseModel):
    enabled: bool


def build_developer_router() -> Any:
    from fastapi import APIRouter, HTTPException

    router = APIRouter()

    @router.get("/developer/ui")
    def developer_ui(ports: AppPortsDep) -> DeveloperUIResponse:
        return DeveloperUIResponse(
            show_dev_tools_ui=ports.settings.developer_show_dev_tools_ui,
            prompt_echo=ports.developer.prompt_echo,
        )

    @router.put("/developer/prompt-echo")
    def developer_set_prompt_echo(
        body: PromptEchoBody,
        ports: AppPortsDep,
    ) -> dict[str, bool]:
        if not ports.settings.developer_show_dev_tools_ui:
            raise HTTPException(
                status_code=403,
                detail="配置 developer.show_dev_tools_ui 为 false，禁止运行时切换。",
            )
        ports.developer.prompt_echo = body.enabled
        return {"prompt_echo": body.enabled}

    @router.get("/developer/agent-tools")
    def developer_agent_tools(
        ports: AppPortsDep,
        retrieval: RetrievalDep,
    ) -> dict[str, Any]:
        """列出当前会注入对话的 Agent 工具名（含 MCP）；仅开发 UI 开启时可用。"""
        if not ports.settings.developer_show_dev_tools_ui:
            raise HTTPException(
                status_code=403,
                detail="配置 developer.show_dev_tools_ui 为 false，禁止查看。",
            )
        from logos.platform.mcp_stdio import resolve_repo_root
        from logos.platform.sg_layer import build_v01_guarded_tool_registry

        repo = resolve_repo_root()
        reg = build_v01_guarded_tool_registry(
            ports.settings,
            retrieval=retrieval,
        )
        mcp_status: list[dict[str, Any]] = []
        for e in ports.settings.mcp_servers:
            script = (repo / e.entrypoint).resolve()
            mcp_status.append(
                {
                    "id": e.id,
                    "enabled": e.enabled,
                    "entrypoint": e.entrypoint,
                    "entrypoint_exists": script.is_file(),
                    "strip_http_proxy": e.strip_http_proxy,
                }
            )
        return {
            "tools": sorted(reg.names()),
            "mcp_servers": mcp_status,
            "repo_root_resolved": str(repo),
        }

    return router
