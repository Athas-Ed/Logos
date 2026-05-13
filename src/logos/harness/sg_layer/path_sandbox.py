"""草稿与文件类工具的路径沙箱：禁止逃出 Config 指定的 workspace 根。"""

from __future__ import annotations

from pathlib import Path


class PathSandboxViolationError(ValueError):
    """用户路径无法解析为 workspace 下的安全路径。"""


def resolve_path_under_root(root: Path, user_path: str) -> Path:
    """将 *user_path* 解析为 *root* 下的绝对路径；失败则抛 :class:`PathSandboxViolationError`。

    规则（V0.1）：
    - 仅允许相对路径片段，禁止绝对路径；
    - 禁止任何 ``..`` 段（在规范化前检查）；
    - 解析后必须仍在 *root* 的规范路径之下（防符号链接逃逸）。
    """
    root_resolved = root.resolve()
    raw = (user_path or "").strip()
    if not raw:
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
        msg = "路径解析后落在 workspace 之外"
        raise PathSandboxViolationError(msg) from e

    return full


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
