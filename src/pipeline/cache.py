"""Cache em 2 niveis: exact-match (SHA256) + semantic (cosine similarity).

Reaproveita o notebook 05.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


class ExactCache:
    """Cache por hash SHA256 da query. Captura replays exatos (~10-15% das queries)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    @staticmethod
    def _key(query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()

    def get(self, query: str) -> str | None:
        return self._store.get(self._key(query))

    def put(self, query: str, answer: str) -> None:
        self._store[self._key(query)] = answer

    def stats(self) -> dict[str, int]:
        return {"size": len(self._store)}


class SemanticCache:
    """Cache por similaridade de embedding. Captura parafrases (~20% adicional)."""

    _model: SentenceTransformer | None = None

    def __init__(self, threshold: float = 0.93) -> None:
        self.threshold = threshold
        self._queries: list[str] = []
        self._embeddings: list[np.ndarray] = []
        self._answers: list[str] = []

        if SemanticCache._model is None:
            SemanticCache._model = SentenceTransformer("all-MiniLM-L6-v2")

    def _embed(self, text: str) -> np.ndarray:
        return SemanticCache._model.encode(text)

    # ------------------------------------------------------------------ TODO 5
    def get(self, query: str) -> str | None:
        """Retorna resposta cacheada se similar a query alguma anterior, OU None."""
        if not self._queries:
            return None

        query_emb = self._embed(query)
        best_sim = -1.0
        best_idx = -1

        for idx, stored_emb in enumerate(self._embeddings):
            cos_sim = np.dot(query_emb, stored_emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(stored_emb)
            )
            if cos_sim > best_sim:
                best_sim = cos_sim
                best_idx = idx

        if best_sim >= self.threshold and best_idx >= 0:
            return self._answers[best_idx]
        return None

    def put(self, query: str, answer: str) -> None:
        self._queries.append(query)
        self._embeddings.append(self._embed(query))
        self._answers.append(answer)

    def stats(self) -> dict[str, Any]:
        return {"size": len(self._queries), "threshold": self.threshold}
