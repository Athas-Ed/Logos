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


def extract_entity_id(headers: dict[str, Any], *, rel_posix: str) -> str:
    """entity_id from YAML, else numeric segment from `entities/<id>/`."""
    eid = headers.get("entity_id")
    if isinstance(eid, str) and eid.strip():
        return eid.strip()
    m = re.search(r"(?:^|/)entities/(\d+)/", rel_posix)
    if m:
        return m.group(1)
    return "unknown"


def extract_title(headers: dict[str, Any], *, body: str, fallback_name: str) -> str:
    t = headers.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip() or fallback_name
    return fallback_name
