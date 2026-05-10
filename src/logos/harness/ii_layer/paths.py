from __future__ import annotations

from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """自 *start* 向上查找含 ``pyproject.toml`` 与 ``src/logos`` 的仓库根（兼容可编辑安装路径）。"""
    for base in [start, *start.parents]:
        if (base / "pyproject.toml").is_file() and (base / "src" / "logos").is_dir():
            return base
    # 回退：原相对深度（旧布局）
    return start.parents[4]


def default_gui_dist_dir() -> Path:
    """解析 ``<repo>/src/gui/dist``（不依赖当前工作目录）。"""
    here = Path(__file__).resolve()
    return _find_repo_root(here) / "src" / "gui" / "dist"
