"""KSFS 目录列举（纯 pathlib + 沙箱规则，供 S&G 注册为 Agent 工具）。"""

from __future__ import annotations

import json
from pathlib import Path

from logos.paths import PathSandboxViolationError, resolve_path_under_root


def list_ksfs_entries(
    ksfs_root: Path,
    relative_dir: str = "",
    *,
    recursive: bool = False,
    max_entries: int = 200,
) -> str:
    """列出 KSFS 根下某子目录条目，返回 JSON 字符串。"""
    cap = max(1, min(int(max_entries), 1000))
    root_r = ksfs_root.resolve()
    try:
        base = resolve_path_under_root(root_r, relative_dir, allow_empty=True)
    except PathSandboxViolationError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    if not base.exists():
        return json.dumps(
            {"error": f"路径不存在：{relative_dir or '.'!r}"}, ensure_ascii=False
        )
    if base.is_file():
        rel = base.relative_to(root_r).as_posix()
        return json.dumps(
            {"entries": [{"kind": "file", "name": base.name, "path": rel}], "truncated": False},
            ensure_ascii=False,
        )

    out: list[dict[str, str]] = []

    def rel_of(p: Path) -> str:
        return p.resolve().relative_to(root_r).as_posix()

    if not recursive:
        try:
            for entry in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if entry.name.startswith("."):
                    continue
                kind = "dir" if entry.is_dir() else "file"
                if kind == "file" and entry.suffix.lower() not in (
                    ".md",
                    ".markdown",
                    ".txt",
                ):
                    continue
                out.append(
                    {"kind": kind, "name": entry.name, "path": rel_of(entry)}
                )
                if len(out) >= cap:
                    break
        except OSError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        return json.dumps(
            {"entries": out, "truncated": len(out) >= cap},
            ensure_ascii=False,
        )

    stack = [base]
    while stack and len(out) < cap:
        d = stack.pop()
        try:
            children = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except OSError:
            continue
        for entry in children:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                stack.append(entry)
                out.append({"kind": "dir", "name": entry.name, "path": rel_of(entry)})
            else:
                if entry.suffix.lower() not in (".md", ".markdown", ".txt"):
                    continue
                out.append({"kind": "file", "name": entry.name, "path": rel_of(entry)})
            if len(out) >= cap:
                break

    return json.dumps(
        {"entries": out, "truncated": len(out) >= cap},
        ensure_ascii=False,
    )
