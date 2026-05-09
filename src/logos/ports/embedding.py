from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TextEmbedder(Protocol):
    """将文本块映射为稠密向量（可替换实现；由配置驱动）。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """每个输入文本对应一个向量，顺序与 *texts* 一致。"""
        ...
