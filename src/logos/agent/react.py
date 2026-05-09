"""ReAct loop helpers (single-tool step per iteration)."""

from __future__ import annotations

from dataclasses import dataclass

from logos.ports.llm import ChatMessage, LLMClient

from logos.agent import cb, json_tools
from logos.agent.tool_registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class ReActResult:
    answer: str
    steps: int
    messages: list[ChatMessage]


def run_react_loop(
    llm: LLMClient,
    registry: ToolRegistry,
    user_text: str,
    *,
    max_steps: int = 16,
    extra_system: str | None = None,
    json_mode: bool = True,
) -> ReActResult:
    """Thought → (optional) tool → observation, until final_answer or cap."""
    messages = cb.seed_messages(registry, user_text, extra_system=extra_system)
    steps = 0
    nudge_budget = 2

    while steps < max_steps:
        steps += 1
        assistant_text = llm.complete(messages, json_mode=json_mode)
        cb.append_assistant(messages, assistant_text)
        step = json_tools.parse_react_json(assistant_text)

        if step.final_answer is not None:
            return ReActResult(answer=step.final_answer, steps=steps, messages=messages)

        if step.action_name:
            obs = registry.execute(step.action_name, step.action_arguments)
            cb.append_observation(messages, obs)
            continue

        if nudge_budget <= 0:
            return ReActResult(
                answer="agent stopped: could not parse a valid JSON step",
                steps=steps,
                messages=messages,
            )
        nudge_budget -= 1
        detail = "missing final_answer and valid action"
        if step.thought:
            detail += f"; thought was: {step.thought[:200]}"
        cb.append_format_nudge(messages, detail)

    return ReActResult(
        answer="agent stopped: max ReAct steps exceeded",
        steps=steps,
        messages=messages,
    )
