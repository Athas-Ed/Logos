"""TaskSession：统一的任务执行入口（deep module）。

一次「任务」从 ``skill_id + user_text`` 到执行完成的所有语义都收敛于此：

- PR 只选一次（``paradigm_override`` 校验也在此）；
- ``task_input`` 合并只发生一次（修复 lossy 语义）；
- prompt_echo 旁路（不调用 executor / LLM）；
- obs TLS 生命周期（prime / reset / clear）自持；
- citations 兜底检索在此；结果以结构化 :class:`TaskDone` 产出，
  展示层（分块、summary 文案、presentation 档位）留给 HTTP。

对外产出统一的 :class:`TaskEvent` 流，隐藏 dialogue/react/plan/pipeline 的范式差异。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from logos.ports.llm import ChatMessage, LLMClient
from logos.ports.retrieval import Citation, RetrievalService
from logos.ports.settings import AppSettings

from logos.agent import cb, dialogue, pipeline, plan, pr, react
from logos.agent.dialogue import DialogueStreamDone, DialogueStreamText
from logos.agent.prompt_echo import format_messages_for_prompt_echo
from logos.agent.tool_registry import ToolRegistry

Paradigm = Literal["dialogue", "react", "plan", "pipeline"]
_VALID_OVERRIDES: frozenset[str] = frozenset({"dialogue", "react", "plan", "pipeline"})


# ═══════════════════════════════════════════════════════════════════
# TaskEvent 统一事件流
# ═══════════════════════════════════════════════════════════════════


class TaskEvent:
    """任务执行过程中的一个事件（各范式统一对外面）。"""


@dataclass(frozen=True, slots=True)
class TaskText(TaskEvent):
    """正文片段（映射 SSE ``delta``；prompt_echo 时为完整回显）。"""

    text: str


@dataclass(frozen=True, slots=True)
class TaskReasoning(TaskEvent):
    """推理片段（映射 SSE ``reasoning_summary`` / ``reasoning_full``）。"""

    text: str


@dataclass(frozen=True, slots=True)
class TaskToolTrace(TaskEvent):
    """工具调用轨迹（映射 SSE ``tool_trace_summary`` / ``tool_trace_full``）。"""

    tool_name: str
    arguments_json: str
    observation: str
    error: str | None


@dataclass(frozen=True, slots=True)
class TaskCitations(TaskEvent):
    """引用结果（映射 SSE ``citations_partial`` / ``citations_full``）。"""

    items: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class TaskPipelineStep(TaskEvent):
    """pipeline 阶段事件（映射 SSE ``pipeline_step``）。"""

    step_id: str
    status: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class TaskPipelineWarning(TaskEvent):
    """pipeline 重叠扫描警告（映射 SSE ``pipeline_warning``）。"""

    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TaskDone(TaskEvent):
    """结构化执行结果。*answer* 为最终正文；*chunked* 表示 HTTP 层需分块发出。"""

    kind: Literal["dialogue", "react", "plan", "pipeline"]
    answer: str = ""
    #: react：final_answer 未流式发过，HTTP 层需 ``_chunk_text`` 分块
    chunked: bool = False
    hit_step_limit: bool = False
    written_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    unit_count: int = 0
    batch_id: str | None = None


# ═══════════════════════════════════════════════════════════════════
# task_input 合并（唯一 merge 点；修复 lossy 语义）
# ═══════════════════════════════════════════════════════════════════


def merge_task_input_into_user(
    user_text: str, task_input: dict[str, Any] | None
) -> str:
    """将结构化任务输入合并进用户文本。

    修复语义：``text`` 与其余结构化键**并存**时全部保留（旧实现中
    ``text`` 存在即提前 return，其余键被静默丢弃）。
    """
    base = user_text.strip()
    if not task_input:
        return base

    parts: list[str] = []
    if base:
        parts.append(base)

    text = task_input.get("text")
    if isinstance(text, str) and text.strip() and text.strip() != base:
        parts.append(f"【任务输入】\n{text.strip()}")

    remaining = {k: v for k, v in task_input.items() if k != "text"}
    if remaining:
        field_lines: list[str] = []
        for key, value in remaining.items():
            if isinstance(value, str) and value.strip():
                field_lines.append(f"{key}：{value.strip()}")
            elif not isinstance(value, str):
                field_lines.append(f"{key}：{value!s}")
        if field_lines:
            parts.append("【任务输入】\n" + "\n".join(field_lines))

    return "\n\n".join(parts).strip() or base


def _allow_paradigm_override(settings: AppSettings) -> bool:
    if settings.developer_show_dev_tools_ui:
        return True
    return os.environ.get("LOGOS_FORCE_STUB_LLM", "").strip() == "1"


# ═══════════════════════════════════════════════════════════════════
# TaskSession
# ═══════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class TaskSession:
    """一次任务执行上下文。

    *workspace_root* / *ksfs_root* 为**已解析**路径（来自 config 层
    ``ResolvedPaths``，本模块不做任何路径解析）。
    """

    llm: LLMClient
    tools: ToolRegistry
    settings: AppSettings
    retrieval: RetrievalService | None = None
    #: 工具注册表写引用的出口；react 分支引用为空时兜底 ``retrieval.query``
    citation_sink: list[Citation] | None = None
    workspace_root: Path | None = None
    ksfs_root: Path | None = None
    prompt_echo: bool = False

    def iter_task(
        self,
        skill_id: str,
        user_text: str,
        *,
        task_input: dict[str, Any] | None = None,
        history: list[ChatMessage] | None = None,
        extra_system: str | None = None,
        max_steps: int | None = None,
        stream_assistant: bool = True,
        paradigm_override: str | None = None,
    ) -> Iterator[TaskEvent]:
        """执行一次任务，产出统一 :class:`TaskEvent` 流。"""
        from logos.platform.obs.tool_chain import (
            clear_obs_log_profile_tls,
            prime_obs_log_profile_for_chat,
            reset_react_tool_steps,
        )

        prime_obs_log_profile_for_chat(
            str(self.settings.obs_log_profile or "standard")
        )
        reset_react_tool_steps()
        try:
            yield from self._dispatch(
                skill_id,
                user_text,
                task_input=task_input,
                history=history,
                extra_system=extra_system,
                max_steps=max_steps,
                stream_assistant=stream_assistant,
                paradigm_override=paradigm_override,
            )
        finally:
            reset_react_tool_steps()
            clear_obs_log_profile_tls()

    # ── 内部：范式分发（PR 只选一次） ──────────────────────────────

    def _dispatch(
        self,
        skill_id: str,
        user_text: str,
        *,
        task_input: dict[str, Any] | None,
        history: list[ChatMessage] | None,
        extra_system: str | None,
        max_steps: int | None,
        stream_assistant: bool,
        paradigm_override: str | None,
    ) -> Iterator[TaskEvent]:
        from logos.platform.skills_config import resolve_skill_config
        from logos.platform.skills_registry import get_skill_manifest

        paradigm = pr.select_paradigm(skill_id, user_text=user_text)
        raw_override = (paradigm_override or "").strip().lower()
        if raw_override in _VALID_OVERRIDES and _allow_paradigm_override(self.settings):
            paradigm = cast(Paradigm, raw_override)

        manifest = get_skill_manifest(skill_id)
        cfg = resolve_skill_config(skill_id, manifest, self.settings)
        eff_steps = (
            max_steps
            if max_steps is not None
            else int(cfg.get("max_steps", self.settings.react_max_steps))
        )

        clipped = list(history or [])
        clip = cfg.get("history_clip_max_full_turns")
        if clip is not None and clipped:
            clipped = cb.clip_turn_history(clipped, max_full_rounds=int(clip))

        merged = merge_task_input_into_user(user_text, task_input)

        if paradigm == "dialogue":
            yield from self._run_dialogue(
                skill_id, merged, history=clipped, extra_system=extra_system
            )
            return
        if paradigm == "plan":
            yield from self._run_plan(
                skill_id, merged, history=clipped, extra_system=extra_system
            )
            return
        if paradigm == "pipeline":
            yield from self._run_pipeline(
                skill_id, merged, extra_system=extra_system
            )
            return
        if paradigm == "react":
            yield from self._run_react(
                skill_id,
                merged,
                user_text_raw=user_text,
                history=clipped,
                extra_system=extra_system,
                max_steps=eff_steps,
                stream_assistant=stream_assistant,
            )
            return
        msg = f"unsupported paradigm: {paradigm!r}"
        raise ValueError(msg)

    # ── 内部：各范式执行 + TaskEvent 翻译 ──────────────────────────

    def _echo_done(self, messages: list[ChatMessage]) -> Iterator[TaskEvent]:
        """prompt_echo 旁路：回显 CB 拼装结果，不调用 LLM / executor。"""
        echo_text = format_messages_for_prompt_echo(messages)
        yield TaskText(text=echo_text)
        yield TaskDone(kind="dialogue", answer=echo_text)

    def _run_dialogue(
        self,
        skill_id: str,
        user_text: str,
        *,
        history: list[ChatMessage],
        extra_system: str | None,
    ) -> Iterator[TaskEvent]:
        if self.prompt_echo:
            messages = cb.seed_dialogue_messages(
                skill_id,
                history,
                user_text,
                extra_system=extra_system,
                registry=self.tools,
            )
            yield from self._echo_done(messages)
            return
        for item in dialogue.iter_dialogue_task(
            self.llm,
            skill_id,
            user_text,
            extra_system=extra_system,
            history=history,
            registry=self.tools,
            stream_assistant=True,
        ):
            if isinstance(item, DialogueStreamText):
                yield TaskText(text=item.text)
            elif isinstance(item, DialogueStreamDone):
                yield TaskDone(kind="dialogue", answer=item.result.answer)

    def _run_plan(
        self,
        skill_id: str,
        user_text: str,
        *,
        history: list[ChatMessage],
        extra_system: str | None,
    ) -> Iterator[TaskEvent]:
        if self.prompt_echo:
            messages = cb.seed_plan_messages(
                skill_id,
                history,
                user_text,
                extra_system=extra_system,
            )
            yield from self._echo_done(messages)
            return
        for item in plan.iter_plan_phase_a(
            self.llm,
            skill_id,
            user_text,
            extra_system=extra_system,
            history=history,
            stream_assistant=True,
        ):
            if isinstance(item, DialogueStreamText):
                yield TaskText(text=item.text)
            elif isinstance(item, DialogueStreamDone):
                yield TaskDone(kind="plan", answer=item.result.answer)

    def _run_pipeline(
        self,
        skill_id: str,
        user_text: str,
        *,
        extra_system: str | None,
    ) -> Iterator[TaskEvent]:
        from logos.platform.skills_registry import get_skill_manifest

        if self.workspace_root is None:
            msg = "workspace_root required for pipeline paradigm"
            raise ValueError(msg)
        manifest = get_skill_manifest(skill_id)
        profile = manifest.pipeline_profile
        if not profile:
            msg = f"skill {skill_id!r} missing pipeline_profile"
            raise ValueError(msg)
        for item in pipeline.iter_run_pipeline(
            self.llm,
            profile_id=profile,
            workspace_root=self.workspace_root,
            ksfs_root=self.ksfs_root,
            user_text=user_text,
            extra_system=extra_system,
        ):
            if isinstance(item, pipeline.PipelineStepEvent):
                yield TaskPipelineStep(
                    step_id=item.step_id,
                    status=item.status,
                    summary=item.summary,
                )
            elif isinstance(item, pipeline.PipelineWarningEvent):
                yield TaskPipelineWarning(warnings=tuple(item.warnings))
            elif isinstance(item, pipeline.PipelineStreamDone):
                result = item.result
                units = result.batch.get("units") or []
                yield TaskDone(
                    kind="pipeline",
                    written_paths=tuple(result.written_paths),
                    warnings=tuple(result.warnings),
                    unit_count=len(units),
                    batch_id=result.batch.get("batch_id"),
                )

    def _run_react(
        self,
        skill_id: str,
        user_text: str,
        *,
        user_text_raw: str,
        history: list[ChatMessage],
        extra_system: str | None,
        max_steps: int,
        stream_assistant: bool,
    ) -> Iterator[TaskEvent]:
        from logos.platform.sg_layer.guarded_registry import V01_SG_TOOL_WHITELIST

        extra = extra_system or ""
        mcp_tool_names = frozenset(self.tools.names()) - V01_SG_TOOL_WHITELIST
        if mcp_tool_names:
            listed = ", ".join(sorted(mcp_tool_names))
            extra += (
                f"\n\n【工具】以下 MCP 暴露的工具已启用：{listed}。"
                "按用户意图在恰当时机调用；与 KSFS 无关的查询不必先 retrieve。"
            )

        if self.prompt_echo:
            messages = cb.seed_messages_with_history(
                self.tools,
                history,
                user_text,
                extra_system=extra or None,
                skill_id=skill_id,
            )
            echo_text = format_messages_for_prompt_echo(messages)
            yield TaskText(text=echo_text)
            yield TaskDone(kind="react", answer=echo_text)
            return

        done_item: react.ReActStreamDone | None = None
        for item in react.iter_react_loop(
            self.llm,
            self.tools,
            user_text,
            max_steps=max_steps,
            extra_system=extra or None,
            history=history,
            stream_assistant=stream_assistant,
            skill_id=skill_id,
        ):
            if isinstance(item, react.ReActStreamReasoning):
                yield TaskReasoning(text=item.text)
            elif isinstance(item, react.ReActStreamToolTrace):
                yield TaskToolTrace(
                    tool_name=item.tool_name,
                    arguments_json=item.arguments_json,
                    observation=item.observation,
                    error=item.error,
                )
            elif isinstance(item, react.ReActStreamDone):
                done_item = item
                cites = list(self.citation_sink or [])
                if not cites and self.retrieval is not None:
                    cites = self.retrieval.query(text=user_text_raw, top_k=8)
                if cites:
                    yield TaskCitations(items=tuple(cites))
                yield TaskDone(
                    kind="react",
                    answer=item.result.answer,
                    chunked=True,
                    hit_step_limit=item.result.hit_step_limit,
                )
        if done_item is None:
            msg = "react 未返回结束状态"
            raise RuntimeError(msg)
