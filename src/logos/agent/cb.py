"""Context builder: ReAct / dialogue system messages and prompt fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from logos.platform.mcp_stdio import resolve_repo_root
from logos.ports.llm import ChatMessage

from logos.agent.tool_registry import ToolRegistry

REACT_JSON_MANDATE_MARKERS = (
    "每一轮必须只回复**一个** JSON",
    '{"thought"',
)

_PROMPTS_ROOT: Path | None = None


def prompts_root() -> Path:
    global _PROMPTS_ROOT  # noqa: PLW0603
    if _PROMPTS_ROOT is None:
        _PROMPTS_ROOT = resolve_repo_root() / "resources" / "prompts"
    return _PROMPTS_ROOT


def load_prompt_fragment(relative_path: str) -> str:
    """加载 ``resources/prompts/`` 下片段；缺失返回空串。"""
    rel = relative_path.replace("\\", "/").lstrip("/")
    path = prompts_root() / rel
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _merge_task_input_into_user(user_text: str, task_input: dict[str, Any] | None) -> str:
    base = user_text.strip()
    if not task_input:
        return base
    lines = [base] if base else []
    text = task_input.get("text")
    if isinstance(text, str) and text.strip():
        if not base or text.strip() != base:
            lines.append(f"【任务输入】\n{text.strip()}")
    else:
        try:
            import json

            lines.append("【任务输入】\n" + json.dumps(task_input, ensure_ascii=False))
        except (TypeError, ValueError):
            lines.append(f"【任务输入】\n{task_input!s}")
    return "\n\n".join(lines).strip() or base


def build_plan_system_message(
    skill_id: str,
    *,
    extra_system: str | None = None,
) -> str:
    """Plan Phase A system：要求输出含步骤列表的 JSON 或 Markdown（无 ReAct JSON 协议）。"""
    from logos.platform.skills_registry import get_skill_manifest

    manifest = get_skill_manifest(skill_id)
    parts = [
        load_prompt_fragment("paradigms/plan/base.md"),
        load_prompt_fragment(f"{manifest.prompt_runtime_key}.md"),
    ]
    system = "\n\n".join(p for p in parts if p) or "Plan 范式 Phase A。"
    if extra_system:
        system = system + "\n\n" + extra_system.strip()
    return system


def seed_plan_messages(
    skill_id: str,
    history: list[ChatMessage],
    user_text: str,
    *,
    extra_system: str | None = None,
    task_input: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    """system + 历史 + 当前 user（Plan Phase A）。"""
    system = build_plan_system_message(skill_id, extra_system=extra_system)
    out: list[ChatMessage] = [ChatMessage(role="system", content=system)]
    out.extend(history)
    out.append(
        ChatMessage(
            role="user",
            content=_merge_task_input_into_user(user_text, task_input),
        )
    )
    return out


def build_dialogue_system_message(
    skill_id: str,
    registry: ToolRegistry | None = None,
    *,
    extra_system: str | None = None,
) -> str:
    """对话范式 system：无 ReAct JSON-only 条令。"""
    from logos.platform.skills_registry import get_skill_manifest

    manifest = get_skill_manifest(skill_id)
    parts = [
        load_prompt_fragment("paradigms/dialogue/base.md"),
        load_prompt_fragment(f"paradigms/dialogue/persistence/{manifest.persistence_tier}.md"),
        load_prompt_fragment(f"{manifest.prompt_runtime_key}.md"),
    ]
    system = "\n\n".join(p for p in parts if p)
    if registry is not None and registry.names():
        tools = registry.tools_prompt_section()
        system += (
            "\n\n【可用工具】以下工具已启用（由宿主按需调用，勿使用 ReAct JSON 协议）：\n"
            f"{tools}"
        )
    if extra_system:
        system = system + "\n\n" + extra_system.strip()
    return system


def compose_prompt(
    paradigm: str,
    persistence_tier: str,
    skill_id: str,
    registry: ToolRegistry | None = None,
    *,
    extra_system: str | None = None,
) -> str:
    """按范式 × 档位拼装 L2 system 文本（供单测与 CB 复用）。"""
    if paradigm == "dialogue":
        return build_dialogue_system_message(
            skill_id, registry, extra_system=extra_system
        )
    if paradigm == "react":
        if registry is None:
            msg = "compose_prompt(react) requires registry"
            raise ValueError(msg)
        system = build_react_system_message(registry)
        if extra_system:
            system = system + "\n\n" + extra_system.strip()
        return system
    if paradigm == "plan":
        return build_plan_system_message(skill_id, extra_system=extra_system)
    _ = persistence_tier
    msg = f"compose_prompt unsupported paradigm: {paradigm!r}"
    raise ValueError(msg)


def seed_dialogue_messages(
    skill_id: str,
    history: list[ChatMessage],
    user_text: str,
    *,
    extra_system: str | None = None,
    registry: ToolRegistry | None = None,
    task_input: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    """system + 历史 + 当前 user（对话范式，无 ReAct JSON 头）。"""
    system = build_dialogue_system_message(skill_id, registry, extra_system=extra_system)
    out: list[ChatMessage] = [ChatMessage(role="system", content=system)]
    out.extend(history)
    out.append(
        ChatMessage(
            role="user",
            content=_merge_task_input_into_user(user_text, task_input),
        )
    )
    return out


def load_operating_mode_suffix(mode: str) -> str:
    """运行模式后缀：``resources/prompts/modes/{author|screenwriter}.md``。"""
    m = (mode or "author").strip().lower()
    rel = "modes/screenwriter.md" if m == "screenwriter" else "modes/author.md"
    return load_prompt_fragment(rel)


def build_react_system_message(registry: ToolRegistry) -> str:
    tools = registry.tools_prompt_section()
    template = load_prompt_fragment("paradigms/react/base.md")
    if not template:
        msg = "missing resources/prompts/paradigms/react/base.md"
        raise FileNotFoundError(msg)
    if "{{TOOLS_JSON}}" in template:
        return template.replace("{{TOOLS_JSON}}", tools)
    return template + "\n工具目录（JSON 数组）：\n" + tools


def seed_messages(
    registry: ToolRegistry,
    user_text: str,
    *,
    extra_system: str | None = None,
) -> list[ChatMessage]:
    """Initial messages for a ReAct session."""
    return seed_messages_with_history(
        registry,
        [],
        user_text,
        extra_system=extra_system,
    )


def seed_messages_with_history(
    registry: ToolRegistry,
    history: list[ChatMessage],
    user_text: str,
    *,
    extra_system: str | None = None,
) -> list[ChatMessage]:
    """system + 历史 user/assistant 轮次 + 当前 user（*history* 不含 system）。"""
    system = build_react_system_message(registry)
    if extra_system:
        system = system + "\n\n" + extra_system.strip()
    out: list[ChatMessage] = [ChatMessage(role="system", content=system)]
    out.extend(history)
    out.append(ChatMessage(role="user", content=user_text.strip()))
    return out


def append_assistant(messages: list[ChatMessage], content: str) -> None:
    messages.append(ChatMessage(role="assistant", content=content))


def append_observation(messages: list[ChatMessage], observation: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content="工具观测结果：\n" + observation.strip(),
        )
    )


def append_format_nudge(messages: list[ChatMessage], detail: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content=(
                "你上一轮输出不是符合约定的单个 JSON 对象。请重新回复，且**仅包含**一个 JSON 对象（键名仍为英文）。"
                f"\n说明：{detail}"
            ),
        )
    )


def _split_message_turns(
    history: list[ChatMessage],
) -> list[tuple[ChatMessage, ChatMessage | None]]:
    turns: list[tuple[ChatMessage, ChatMessage | None]] = []
    i = 0
    while i < len(history):
        m = history[i]
        if m.role != "user":
            i += 1
            continue
        assistant = history[i + 1] if i + 1 < len(history) and history[i + 1].role == "assistant" else None
        turns.append((m, assistant))
        i += 2 if assistant is not None else 1
    return turns


def _one_line_turn_title(user_text: str, turn_index: int) -> str:
    t = user_text.strip().replace("\n", " ")
    while "  " in t:
        t = t.replace("  ", " ")
    preview = t if len(t) <= 40 else t[:39] + "…"
    return f"【第{turn_index + 1}轮】用户问：{preview or '（空）'}"


def clip_turn_history(
    history: list[ChatMessage],
    *,
    max_full_rounds: int = 5,
) -> list[ChatMessage]:
    """连续问答：最近 *max_full_rounds* 轮全文，更早轮仅一行 title。"""
    turns = _split_message_turns(history)
    if not turns:
        return []
    n = max(1, max_full_rounds)
    out: list[ChatMessage] = []
    older_count = max(0, len(turns) - n)
    for i in range(older_count):
        title = _one_line_turn_title(turns[i][0].content, i)
        out.append(ChatMessage(role="user", content=title))
        out.append(
            ChatMessage(
                role="assistant",
                content="（该轮详情已省略，见后续轮次或档 B 归档。）",
            )
        )
    for i in range(older_count, len(turns)):
        user_m, asst_m = turns[i]
        out.append(user_m)
        if asst_m is not None:
            out.append(ChatMessage(role="assistant", content=asst_m.content))
    return out
