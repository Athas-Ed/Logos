"""统一路径安全模块：用户路径在根下的沙箱解析（Candidate 3 单一来源）。

所有需要把「用户提供的相对路径」解析到某个根目录之下的代码，
必须经 :func:`resolve_path_under_root` 或本文档级包装，禁止各自实现。
"""

from __future__ import annotations

from pathlib import Path


class PathSandboxViolationError(ValueError):
    """用户路径无法解析为根下的安全路径。"""


def resolve_path_under_root(
    root: Path,
    user_path: str,
    *,
    allow_empty: bool = False,
) -> Path:
    """将 *user_path* 解析为 *root* 下的绝对路径；失败抛 :class:`PathSandboxViolationError`。

    规则：
    - 空路径默认拒绝；*allow_empty* 时返回 *root* 本身（列根语义）；
    - 仅允许相对路径片段，禁止绝对路径；
    - 禁止 ``..`` 段（在规范化前检查）；
    - 解析后必须仍在 *root* 的规范路径之下（防符号链接逃逸）。
    """
    root_resolved = root.resolve()
    raw = (user_path or "").strip().replace("\\", "/")
    if not raw:
        if allow_empty:
            return root_resolved
        msg = "路径不能为空"
        raise PathSandboxViolationError(msg)

    candidate = Path(raw)
    if candidate.is_absolute():
        msg = "不允许使用绝对路径"
        raise PathSandboxViolationError(msg)

    parts = candidate.parts
    if ".." in parts:
        msg = "路径中不允许出现 .."
        raise PathSandboxViolationError(msg)

    full = (root_resolved / candidate).resolve()
    try:
        full.relative_to(root_resolved)
    except ValueError as e:
        msg = "路径解析后落在根目录之外"
        raise PathSandboxViolationError(msg) from e

    return full


def to_posix_relative(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return rel.as_posix()


def write_draft_under_workspace(workspace_root: Path, path: str, content: str) -> str:
    """整文件写入 *path*（相对 workspace）；成功返回简短说明，失败返回 ``error: ...`` 字符串。"""
    try:
        target = resolve_path_under_root(workspace_root, path)
    except PathSandboxViolationError as exc:
        return f"error: write_draft 被拒绝 — {exc}"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"error: 写入失败 — {exc}"

    rel = target.relative_to(workspace_root.resolve()).as_posix()
    return f"已写入草稿：{rel}（字节数 {len(content.encode('utf-8'))}）"


def read_text_under_root(
    root: Path,
    user_path: str,
    *,
    context_label: str,
    denied_operation: str,
) -> str:
    """只读打开 *root* 下相对路径文本；沙箱规则同 :func:`resolve_path_under_root`。"""
    try:
        target = resolve_path_under_root(root, user_path)
    except PathSandboxViolationError as exc:
        return f"error: {denied_operation} 被拒绝 — {exc}"
    if not target.is_file():
        return f"error: 未找到文件（相对 {context_label}）{user_path!r}"
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        return f"error: 读取失败 — {exc}"
