"""Minimal paradigm router: V0.1 routes everything to ReAct."""

from __future__ import annotations

from typing import Literal

Paradigm = Literal["react"]


def select_paradigm(*_args: object, **_kwargs: object) -> Paradigm:
    """Always ReAct for V0.1 (PR extension point for Plan / other paradigms later)."""
    return "react"
