"""Parse ReAct-style JSON tool steps from model text (stdlib only)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ParsedStep:
    """One model turn after JSON extraction."""

    raw_text: str
    thought: str | None
    action_name: str | None
    action_arguments: dict[str, Any] | None
    final_answer: str | None


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_json_comments(s: str) -> str:
    """Remove // line comments outside strings (good enough for tool JSON)."""
    out: list[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(s):
        ch = s[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(s) and s[i + 1] == "/":
            while i < len(s) and s[i] not in "\n\r":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_json_object(text: str) -> str | None:
    text = text.strip()
    m = _FENCE.search(text)
    if m:
        return m.group(1).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_react_json(text: str) -> ParsedStep:
    """Parse assistant output into thought / tool action / final answer."""
    blob = _extract_json_object(text)
    if not blob:
        return ParsedStep(
            raw_text=text,
            thought=None,
            action_name=None,
            action_arguments=None,
            final_answer=None,
        )
    try:
        data = json.loads(_strip_json_comments(blob))
    except json.JSONDecodeError:
        return ParsedStep(
            raw_text=text,
            thought=None,
            action_name=None,
            action_arguments=None,
            final_answer=None,
        )
    if not isinstance(data, dict):
        return ParsedStep(
            raw_text=text,
            thought=None,
            action_name=None,
            action_arguments=None,
            final_answer=None,
        )
    thought = data.get("thought")
    thought_s = thought if isinstance(thought, str) else None

    final = data.get("final_answer")
    if isinstance(final, str) and final.strip():
        return ParsedStep(
            raw_text=text,
            thought=thought_s,
            action_name=None,
            action_arguments=None,
            final_answer=final,
        )

    action = data.get("action")
    if isinstance(action, dict):
        name = action.get("name")
        args = action.get("arguments")
        if isinstance(name, str) and isinstance(args, dict):
            return ParsedStep(
                raw_text=text,
                thought=thought_s,
                action_name=name,
                action_arguments=dict(args),
                final_answer=None,
            )
        if isinstance(name, str) and args is None:
            return ParsedStep(
                raw_text=text,
                thought=thought_s,
                action_name=name,
                action_arguments={},
                final_answer=None,
            )

    return ParsedStep(
        raw_text=text,
        thought=thought_s,
        action_name=None,
        action_arguments=None,
        final_answer=None,
    )
