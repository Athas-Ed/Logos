"""Context builder: ReAct / dialogue system messages and prompt fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from logos.harness.mcp_stdio import resolve_repo_root
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


def build_dialogue_system_message(
    skill_id: str,
    registry: ToolRegistry | None = None,
    *,
    extra_system: str | None = None,
) -> str:
    """对话范式 system：无 ReAct JSON-only 条令。"""
    from logos.harness.skills_registry import get_skill_manifest

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
        from logos.harness.skills_registry import get_skill_manifest

        base = load_prompt_fragment("paradigms/plan/base.md")
        skill = load_prompt_fragment(
            get_skill_manifest(skill_id).prompt_runtime_key + ".md"
        )
        parts = [p for p in (base, skill) if p]
        system = "\n\n".join(parts) if parts else "Plan 范式。"
        if extra_system:
            system = system + "\n\n" + extra_system.strip()
        return system
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


def build_react_system_message(registry: ToolRegistry) -> str:
    tools = registry.tools_prompt_section()
    return (
        "你是 Agent 的推理模块。每一轮必须只回复**一个** JSON 对象（键名保持英文，与下述示例一致），"
        "不要在该 JSON 外再包一层说明文字：\n"
        "1）若无需工具即可作答："
        '{"thought": "…", "final_answer": "…"}\n'
        "2）若需调用工具："
        '{"thought": "…", "action": {"name": "工具名", "arguments": { … 参数 … }}}\n'
        "每轮最多一次工具调用；name 必须与下方目录中的工具名完全一致。\n"
        "工具目录（JSON 数组）：\n"
        f"{tools}\n"
        "说明：thought / final_answer / action / name / arguments 等字段名请勿改写或翻译。"
    )


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
