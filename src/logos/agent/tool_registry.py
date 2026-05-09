"""Tool registration and dispatch for the decision layer (in-process, no port changes)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


JsonDict = dict[str, Any]
ToolHandler = Callable[..., str]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """A callable tool exposed to the LLM with a JSON-schema-shaped parameter description."""

    name: str
    description: str
    parameters: JsonDict
    handler: ToolHandler

    def schema_block(self) -> str:
        """Compact JSON snippet for system prompts."""
        return json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
            ensure_ascii=False,
        )


class ToolRegistry:
    """Name → tool mapping; duplicate names raise at registration time."""

    __slots__ = ("_tools",)

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        *,
        description: str,
        parameters: JsonDict,
        handler: ToolHandler,
    ) -> None:
        if name in self._tools:
            msg = f"tool already registered: {name!r}"
            raise ValueError(msg)
        self._tools[name] = RegisteredTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def tools_prompt_section(self) -> str:
        blocks = [t.schema_block() for t in self._tools.values()]
        return "[\n" + ",\n".join(blocks) + "\n]" if blocks else "[]"

    def execute(self, name: str, arguments: Mapping[str, Any] | None) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"error: unknown tool {name!r}"
        args = dict(arguments or {})
        try:
            return tool.handler(**args)
        except TypeError as exc:
            return f"error: invalid arguments for {name!r}: {exc}"
