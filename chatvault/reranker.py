"""Cross-encoder reranker for ChatVault search results."""
from __future__ import annotations

from typing import Any

from chatvault.search import SearchResult


class Reranker:
    """Lazy-loaded cross-encoder reranker using sentence-transformers."""

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self) -> None:
        self._model = None

    def _load_model(self) -> None:
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.MODEL_NAME)

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if not results:
            return []
        self._load_model()
        pairs = [(query, r.text) for r in results]
        scores = self._model.predict(pairs)
        scored = list(zip(results, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        reranked = []
        for r, s in scored[:top_k]:
            r.score = float(s)
            reranked.append(r)
        return reranked

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
