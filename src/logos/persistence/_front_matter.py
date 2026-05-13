"""Minimal YAML front matter parsing (stdlib only)."""

from __future__ import annotations

import re
from typing import Any


_FM_BLOCK = re.compile(
    r"^---[ \t]*\r?\n(?P<body>.*?)\r?\n---[ \t]*\r?\n(?P<rest>.*)",
    re.DOTALL | re.MULTILINE,
)


def _parse_simple_yaml_map(block: str) -> dict[str, str]:
    """Parse flat `key: value` lines; values may be quoted."""
    out: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return (header dict, markdown body). Missing front matter -> ({}, full text)."""
    m = _FM_BLOCK.match(text)
    if not m:
        return {}, text
    headers = _parse_simple_yaml_map(m.group("body"))
    return headers, m.group("rest")


def _strip_scalar(value: Any) -> str | None:
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    return None


def extract_declared_id(headers: dict[str, Any], *, rel_posix: str) -> str | None:
    """Prefer ``id`` then ``entity_id`` in front matter; else ``entities/<digits>/`` in path."""
    for key in ("id", "entity_id"):
        raw = _strip_scalar(headers.get(key))
        if raw is not None:
            return raw
    m = re.search(r"(?:^|/)entities/(\d+)/", rel_posix)
    if m:
        return m.group(1)
    return None


def extract_entity_id(headers: dict[str, Any], *, rel_posix: str) -> str:
    """Stable entity id for HSI: ``id`` / ``entity_id`` / path segment, else ``unknown``."""
    declared = extract_declared_id(headers, rel_posix=rel_posix)
    if declared is not None:
        return declared
    return "unknown"


def _is_numeric_entity_id(value: str) -> bool:
    return bool(value) and value.isdigit()


def extract_numeric_entity_id(headers: dict[str, Any], *, rel_posix: str) -> str | None:
    """Return declared id only when it is all-digits (KSFS §3.2); else None."""
    declared = extract_declared_id(headers, rel_posix=rel_posix)
    if declared is not None and _is_numeric_entity_id(declared):
        return declared
    return None


def ensure_front_matter_id(text: str, entity_id: str) -> tuple[str, bool]:
    """Ensure ``id:`` exists and matches *entity_id*; never strip body. Returns (new_text, changed)."""
    want = entity_id.strip()
    m = _FM_BLOCK.match(text)
    if not m:
        block = f'id: "{want}"\n'
        inserted = f"---\n{block}---\n{text}"
        return inserted, True
    fm_body = m.group("body")
    rest = m.group("rest")
    headers = _parse_simple_yaml_map(fm_body)
    cur = _strip_scalar(headers.get("id"))
    if cur == want:
        return text, False
    headers["id"] = want
    # Stable, readable ordering: id first, then remaining keys in prior file order.
    ordered_keys: list[str] = []
    seen: set[str] = set()
    for raw_line in fm_body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key in headers and key not in seen:
            ordered_keys.append(key)
            seen.add(key)
    for key in headers:
        if key not in seen:
            ordered_keys.append(key)
            seen.add(key)
    lines_out: list[str] = []
    for key in ordered_keys:
        val = headers[key]
        if any(ch in val for ch in ("\n", "\r", '"')):
            escaped = json_escape_yaml_string(val)
            lines_out.append(f'{key}: "{escaped}"')
        else:
            lines_out.append(f'{key}: "{val}"')
    new_fm = "\n".join(lines_out) + "\n"
    new_text = f"---\n{new_fm}---\n{rest}"
    return new_text, True


def json_escape_yaml_string(value: str) -> str:
    """Minimal escaping for double-quoted YAML scalars."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def extract_title(headers: dict[str, Any], *, body: str, fallback_name: str) -> str:
    t = headers.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip() or fallback_name
    return fallback_name
