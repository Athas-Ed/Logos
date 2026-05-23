"""将配置中的相对路径解析为绝对路径（以仓库根为基准）。"""

from __future__ import annotations

from pathlib import Path


def resolve_under_repo(repo_root: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = repo_root / p
    return p.resolve()


def resolve_conversations_cache_abs(repo_root: Path, conversations_cache: str) -> Path:
    return resolve_under_repo(repo_root, conversations_cache)
