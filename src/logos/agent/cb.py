"""Minimal context builder: system instructions + rolling chat for ReAct."""

from __future__ import annotations

from logos.ports.llm import ChatMessage

from logos.agent.tool_registry import ToolRegistry


def build_react_system_message(registry: ToolRegistry) -> str:
    tools = registry.tools_prompt_section()
    return (
        "You are the reasoning module of an agent. You must reply with a single JSON object, "
        "either:\n"
        '1) {"thought": string, "final_answer": string} when you can answer without tools, or\n'
        '2) {"thought": string, "action": {"name": string, "arguments": object}} to call one tool.\n'
        "Only one tool call per turn. Use the exact tool names from the catalog.\n"
        "Tool catalog (JSON array of tools):\n"
        f"{tools}\n"
        "Do not wrap the JSON in prose outside the JSON object."
    )


def seed_messages(
    registry: ToolRegistry,
    user_text: str,
    *,
    extra_system: str | None = None,
) -> list[ChatMessage]:
    """Initial messages for a ReAct session."""
    system = build_react_system_message(registry)
    if extra_system:
        system = system + "\n\n" + extra_system.strip()
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user_text.strip()),
    ]


def append_assistant(messages: list[ChatMessage], content: str) -> None:
    messages.append(ChatMessage(role="assistant", content=content))


def append_observation(messages: list[ChatMessage], observation: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content="Observation:\n" + observation.strip(),
        )
    )


def append_format_nudge(messages: list[ChatMessage], detail: str) -> None:
    messages.append(
        ChatMessage(
            role="user",
            content=(
                "Your last message was not valid JSON with the required shape. "
                "Respond again with only one JSON object as specified. "
                f"Detail: {detail}"
            ),
        )
    )
