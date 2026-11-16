"""Re-orders search results with a small local cross-encoder model."""

import logging

from fastembed.rerank.cross_encoder import TextCrossEncoder

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Double-checks search results by reading each question and passage together, so the best passages come first."


class Reranker:
    MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"

    def __init__(self, settings: Settings):
        self._cache_dir = str(settings.models_dir / "fastembed")
        self._encoder = None

    def score(self, query: str, texts: list[str]) -> list[float]:
        """One score per text, in input order; higher means more relevant."""
        if not texts:
            return []
        if self._encoder is None:
            log.info("Loading reranker %s", self.MODEL)
            self._encoder = TextCrossEncoder(self.MODEL, cache_dir=self._cache_dir)
        return [float(s) for s in self._encoder.rerank(query, texts)]
