"""Safe path helpers under a single root."""

from __future__ import annotations

from pathlib import Path


def to_posix_relative(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return rel.as_posix()


def resolve_under_root(root: Path, relative_posix: str) -> Path:
    """Resolve `relative_posix` under `root`; raise if escapes."""
    root_r = root.resolve()
    parts = relative_posix.replace("\\", "/").split("/")
    candidate = root_r.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_r)
    except ValueError as e:
        raise ValueError(f"path escapes root: {relative_posix!r}") from e
    return candidate
