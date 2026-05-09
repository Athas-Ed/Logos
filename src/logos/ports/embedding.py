from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TextEmbedder(Protocol):
    """Maps text chunks to dense vectors (replaceable; config-driven)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text; same order as *texts*."""
        ...
