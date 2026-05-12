"""Agent Shell: wires PR (paradigm) + CB (context) + ReAct + tools + LLM port."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import pr, react
from logos.agent.tool_registry import ToolRegistry


@dataclass(slots=True)
class AgentShell:
    """Thin orchestration over `LLMClient` with in-process tools (DIP-friendly)."""

    llm: LLMClient
    tools: ToolRegistry

    def run_task(
        self,
        user_text: str,
        *,
        max_steps: int = 16,
        extra_system: str | None = None,
        json_mode: bool = True,
        history: list[ChatMessage] | None = None,
    ) -> react.ReActResult:
        paradigm = pr.select_paradigm(user_text)
        if paradigm != "react":
            msg = f"unsupported paradigm: {paradigm!r}"
            raise ValueError(msg)
        return react.run_react_loop(
            self.llm,
            self.tools,
            user_text,
            max_steps=max_steps,
            extra_system=extra_system,
            json_mode=json_mode,
            history=history,
        )

    def iter_run_task(
        self,
        user_text: str,
        *,
        max_steps: int = 16,
        extra_system: str | None = None,
        json_mode: bool = True,
        history: list[ChatMessage] | None = None,
        stream_assistant: bool = True,
    ) -> Iterator[
        react.ReActStreamReasoning | react.ReActStreamToolTrace | react.ReActStreamDone
    ]:
        paradigm = pr.select_paradigm(user_text)
        if paradigm != "react":
            msg = f"unsupported paradigm: {paradigm!r}"
            raise ValueError(msg)
        yield from react.iter_react_loop(
            self.llm,
            self.tools,
            user_text,
            max_steps=max_steps,
            extra_system=extra_system,
            json_mode=json_mode,
            history=history,
            stream_assistant=stream_assistant,
        )
