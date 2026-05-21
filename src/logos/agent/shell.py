"""Agent Shell: wires PR (paradigm) + CB (context) + executors + tools + LLM port."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import dialogue, pr, react
from logos.agent.dialogue import DialogueStreamDone, DialogueStreamText
from logos.agent.tool_registry import ToolRegistry


@dataclass(slots=True)
class AgentShell:
    """Thin orchestration over `LLMClient` with in-process tools (DIP-friendly)."""

    llm: LLMClient
    tools: ToolRegistry
    #: 为 True 时不调用 LLM，将 CB 拼装后的完整 messages 作为唯一答复（见 ``developer.prompt_echo``）。
    prompt_echo: bool = False

    def run_task(
        self,
        user_text: str,
        *,
        skill_id: str,
        max_steps: int = 16,
        extra_system: str | None = None,
        json_mode: bool = True,
        history: list[ChatMessage] | None = None,
        task_input: dict[str, Any] | None = None,
    ) -> react.ReActResult | dialogue.DialogueResult:
        paradigm = pr.select_paradigm(skill_id, user_text=user_text)
        if paradigm == "dialogue":
            for item in dialogue.iter_dialogue_task(
                self.llm,
                skill_id,
                user_text,
                extra_system=extra_system,
                history=history,
                registry=self.tools,
                task_input=task_input,
                stream_assistant=False,
                prompt_echo=self.prompt_echo,
            ):
                if isinstance(item, DialogueStreamDone):
                    return item.result
            msg = "dialogue 未返回结束状态"
            raise RuntimeError(msg)
        if paradigm != "react":
            msg = f"unsupported paradigm for run_task: {paradigm!r}"
            raise ValueError(msg)
        return react.run_react_loop(
            self.llm,
            self.tools,
            user_text,
            max_steps=max_steps,
            extra_system=extra_system,
            json_mode=json_mode,
            history=history,
            prompt_echo=self.prompt_echo,
        )

    def iter_run_react_task(
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
        yield from react.iter_react_loop(
            self.llm,
            self.tools,
            user_text,
            max_steps=max_steps,
            extra_system=extra_system,
            json_mode=json_mode,
            history=history,
            stream_assistant=stream_assistant,
            prompt_echo=self.prompt_echo,
        )

    def iter_paradigm_task(
        self,
        skill_id: str,
        user_text: str,
        *,
        max_steps: int = 16,
        extra_system: str | None = None,
        history: list[ChatMessage] | None = None,
        task_input: dict[str, Any] | None = None,
        stream_assistant: bool = True,
    ) -> Iterator[
        DialogueStreamText
        | DialogueStreamDone
        | react.ReActStreamReasoning
        | react.ReActStreamToolTrace
        | react.ReActStreamDone
    ]:
        """按 manifest 范式调度执行器（PR → Shell）。"""
        paradigm = pr.select_paradigm(skill_id, user_text=user_text)
        if paradigm == "dialogue":
            yield from dialogue.iter_dialogue_task(
                self.llm,
                skill_id,
                user_text,
                extra_system=extra_system,
                history=history,
                registry=self.tools,
                task_input=task_input,
                stream_assistant=stream_assistant,
                prompt_echo=self.prompt_echo,
            )
            return
        if paradigm == "react":
            yield from self.iter_run_react_task(
                user_text,
                max_steps=max_steps,
                extra_system=extra_system,
                json_mode=True,
                history=history,
                stream_assistant=stream_assistant,
            )
            return
        msg = f"unsupported paradigm: {paradigm!r}"
        raise ValueError(msg)

    def iter_run_task(
        self,
        user_text: str,
        *,
        skill_id: str,
        max_steps: int = 16,
        extra_system: str | None = None,
        json_mode: bool = True,
        history: list[ChatMessage] | None = None,
        task_input: dict[str, Any] | None = None,
        stream_assistant: bool = True,
    ) -> Iterator[
        DialogueStreamText
        | DialogueStreamDone
        | react.ReActStreamReasoning
        | react.ReActStreamToolTrace
        | react.ReActStreamDone
    ]:
        """兼容入口：须传 ``skill_id``，委托 :meth:`iter_paradigm_task`。"""
        _ = json_mode
        yield from self.iter_paradigm_task(
            skill_id,
            user_text,
            max_steps=max_steps,
            extra_system=extra_system,
            history=history,
            task_input=task_input,
            stream_assistant=stream_assistant,
        )
