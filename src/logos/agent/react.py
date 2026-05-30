"""ReAct loop helpers (single-tool step per iteration)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb, json_tools
from logos.agent.prompt_echo import format_messages_for_prompt_echo
from logos.agent.tool_registry import ToolRegistry
from logos.platform.obs.tool_chain import (
    classify_tool_observation,
    current_obs_profile,
    emit_tool_chain_v1,
    next_react_tool_step_index,
    param_digest_for_log,
)

_log = logging.getLogger("logos.agent.react")

_STEP_CAP_SYNTHESIS_NUDGE = (
    "【系统】本轮 ReAct 步数已达上限，请勿再调用工具。"
    "请仅依据上文中已有的工具观测与用户问题，给出尽可能完整的自然语言作答。"
    "未在观测中出现的内容请勿编造；信息不足请明确说明。"
)


def _last_assistant_text(messages: list[ChatMessage]) -> str | None:
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content.strip():
            return msg.content
    return None


def _coerce_natural_answer(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    step = json_tools.parse_react_json(stripped)
    if step.final_answer and step.final_answer.strip():
        return step.final_answer.strip()
    return stripped


def _synthesize_on_step_cap(
    llm: LLMClient,
    messages: list[ChatMessage],
) -> str:
    """步数触顶时基于已有 observation 强制收束一轮作答。"""
    synth_messages = list(messages)
    synth_messages.append(
        ChatMessage(role="user", content=_STEP_CAP_SYNTHESIS_NUDGE),
    )
    try:
        text = llm.complete(synth_messages, json_mode=False)
    except Exception as exc:  # noqa: BLE001
        _log.warning("步数触顶收束作答失败：%s", exc)
        return ""
    return text.strip()


def _answer_on_step_cap(
    llm: LLMClient,
    messages: list[ChatMessage],
) -> str:
    last = _last_assistant_text(messages)
    if last:
        extracted = _coerce_natural_answer(last)
        if extracted and not extracted.lstrip().startswith("{"):
            return extracted
    body = _synthesize_on_step_cap(llm, messages)
    if body:
        coerced = _coerce_natural_answer(body)
        if coerced:
            return coerced
    if last:
        return _coerce_natural_answer(last)
    return ""


@dataclass(frozen=True, slots=True)
class ReActResult:
    answer: str
    steps: int
    messages: list[ChatMessage]
    hit_step_limit: bool = False


@dataclass(frozen=True, slots=True)
class ReActStreamReasoning:
    """单轮助手输出在流式生成中的一段（多为 JSON 模式下的 token）。"""

    text: str


@dataclass(frozen=True, slots=True)
class ReActStreamDone:
    """ReAct 结束（成功 final_answer、工具循环中止或步数上限）。"""

    result: ReActResult


@dataclass(frozen=True, slots=True)
class ReActStreamToolTrace:
    tool_name: str
    arguments_json: str
    observation: str
    error: str | None


def iter_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
    history: list[ChatMessage] | None = None,
    stream_assistant: bool = True,
    prompt_echo: bool = False,
) -> Iterator[ReActStreamReasoning | ReActStreamToolTrace | ReActStreamDone]:
    """与 :func:`run_react_loop` 相同语义；若 *stream_assistant* 则每轮助手输出以流式片段产出。"""
    messages = cb.seed_messages_with_history(
        registry,
        history or [],
        user_text,
        extra_system=extra_system,
    )
    if prompt_echo:
        echo_text = format_messages_for_prompt_echo(messages)
        yield ReActStreamDone(
            ReActResult(answer=echo_text, steps=0, messages=messages)
        )
        return
    steps = 0
    nudge_budget = 2

    while steps < max_steps:
        steps += 1
        assistant_text = ""
        if stream_assistant:
            for piece in llm.stream_completion(messages, json_mode=json_mode):
                if piece:
                    assistant_text += piece
                    yield ReActStreamReasoning(text=piece)
        else:
            assistant_text = llm.complete(messages, json_mode=json_mode)

        cb.append_assistant(messages, assistant_text)
        step = json_tools.parse_react_json(assistant_text)

        if step.final_answer is not None:
            yield ReActStreamDone(
                ReActResult(answer=step.final_answer, steps=steps, messages=messages)
            )
            return

        if step.action_name:
            args = step.action_arguments or {}
            try:
                args_json = json.dumps(args, ensure_ascii=False)
            except (TypeError, ValueError):
                args_json = "{}"
            prof = current_obs_profile()
            digest = param_digest_for_log(prof, step.action_name, step.action_arguments)
            step_ix = next_react_tool_step_index()
            t0 = time.perf_counter()
            try:
                obs = registry.execute(step.action_name, step.action_arguments)
            except Exception as exc:  # noqa: BLE001
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                emit_tool_chain_v1(
                    step_index=step_ix,
                    tool_name=step.action_name,
                    elapsed_ms=elapsed_ms,
                    status="error",
                    param_digest=digest,
                    error_class=type(exc).__name__,
                )
                yield ReActStreamToolTrace(
                    tool_name=step.action_name,
                    arguments_json=args_json,
                    observation="",
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            st, err_cls = classify_tool_observation(obs)
            emit_tool_chain_v1(
                step_index=step_ix,
                tool_name=step.action_name,
                elapsed_ms=elapsed_ms,
                status=st,
                param_digest=digest,
                error_class=err_cls,
            )
            yield ReActStreamToolTrace(
                tool_name=step.action_name,
                arguments_json=args_json,
                observation=obs,
                error=None,
            )
            cb.append_observation(messages, obs)
            continue

        if nudge_budget <= 0:
            _log.warning(
                "ReAct 在 %d 步内仍无法得到合法 JSON 步骤（已无重试预算），停止循环。",
                steps,
            )
            yield ReActStreamDone(
                ReActResult(
                    answer="已停止：连续多轮无法解析为有效的 JSON 工具步骤。",
                    steps=steps,
                    messages=messages,
                )
            )
            return
        nudge_budget -= 1
        detail = "缺少 final_answer 与合法 action"
        if step.thought:
            detail += f"；thought 摘要：{step.thought[:200]}"
        _log.info("ReAct 输出不完整，追加格式提示：%s", detail[:300])
        cb.append_format_nudge(messages, detail)

    _log.warning("ReAct 达到最大步数上限（%d），仍未结束。", max_steps)
    answer = _answer_on_step_cap(llm, messages)
    yield ReActStreamDone(
        ReActResult(
            answer=answer,
            steps=steps,
            messages=list(messages),
            hit_step_limit=True,
        )
    )


def run_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
    history: list[ChatMessage] | None = None,
    prompt_echo: bool = False,
) -> ReActResult:
    """Thought → (optional) tool → observation, until final_answer or cap（非流式）。"""
    final: ReActResult | None = None
    for item in iter_react_loop(
        llm,
        registry,
        user_text,
        max_steps=max_steps,
        extra_system=extra_system,
        json_mode=json_mode,
        history=history,
        stream_assistant=False,
        prompt_echo=prompt_echo,
    ):
        if isinstance(item, ReActStreamDone):
            final = item.result
    if final is None:
        msg = "iter_react_loop 未产生结束状态"
        raise RuntimeError(msg)
    return final
