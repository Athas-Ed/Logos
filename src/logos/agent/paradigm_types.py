"""Agent 范式类型（与 PR / manifest 共用，避免 harness ↔ agent 循环导入）。"""

from __future__ import annotations

from typing import Literal

Paradigm = Literal["dialogue", "react", "plan", "pipeline"]
