from __future__ import annotations

from pathlib import Path


def default_gui_dist_dir() -> Path:
    """Resolve ``<repo>/src/gui/dist`` from this module location."""
    return Path(__file__).resolve().parents[4] / "src" / "gui" / "dist"
