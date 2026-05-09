from __future__ import annotations

from typing import Any


class BgeSmallZhEmbedder:
    """`TextEmbedder` implementation backed by BAAI bge-small-zh-v1.5 (sentence-transformers)."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model: Any = None

    def _lazy_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - env without torch/ST
            msg = (
                "BgeSmallZhEmbedder requires optional dependency `sentence-transformers` "
                "(and a compatible PyTorch install). "
                "Install e.g. `pip install sentence-transformers`."
            )
            raise ImportError(msg) from e
        self._model = SentenceTransformer(self._model_path)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._lazy_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        out: list[list[float]] = []
        for row in vectors:
            out.append([float(x) for x in row.tolist()])
        return out
