"""Reranking — the second stage of context fusion.

The retrieval router's scores (BM25 term weights, cosine similarity,
RRF fusion scores) are useful for candidate generation but are not
directly comparable to each other and don't model query-chunk relevance
as precisely as a cross-encoder, which attends to the query and chunk
jointly rather than comparing independent embeddings. A CrossEncoder
(``cross-encoder/ms-marco-MiniLM-L-6-v2`` by default) re-scores every
candidate against the query and reorders them.

Two implementations behind one ``Reranker`` protocol:

- ``CrossEncoderReranker`` — the real model, lazily loaded and run off
  the event loop.
- ``PassthroughReranker`` — keeps the retrieval ordering (using the
  retrieval score as the "rerank" score) when the model stack isn't
  available or reranking is disabled; lets the fusion pipeline degrade
  instead of failing the request, and doubles as an ablation baseline
  (rerank on/off) for the paper.
"""

import asyncio
import dataclasses
import importlib.util
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.modules.context_fusion.types import EvidenceChunk

logger = get_logger(__name__)


def cross_encoder_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class Reranker(Protocol):
    model_name: str

    async def rerank(
        self, query: str, candidates: list[EvidenceChunk]
    ) -> list[EvidenceChunk]: ...


class CrossEncoderReranker:
    """Cross-encoder reranker, loaded once and reused across requests."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = asyncio.Lock()

    async def _load(self):
        async with self._lock:
            if self._model is None:
                logger.info("reranker_model_loading", model=self.model_name)
                self._model = await asyncio.to_thread(self._load_sync)
                logger.info("reranker_model_loaded", model=self.model_name)
        return self._model

    def _load_sync(self):
        from sentence_transformers import CrossEncoder

        return CrossEncoder(self.model_name, device="cpu")

    async def rerank(
        self, query: str, candidates: list[EvidenceChunk]
    ) -> list[EvidenceChunk]:
        if not candidates:
            return []
        model = await self._load()
        pairs = [(query, candidate.content) for candidate in candidates]
        scores = await asyncio.to_thread(
            model.predict, pairs, show_progress_bar=False
        )
        rescored = [
            dataclasses.replace(candidate, rerank_score=float(score))
            for candidate, score in zip(candidates, scores)
        ]
        return sorted(rescored, key=lambda c: c.rerank_score, reverse=True)


class PassthroughReranker:
    """No-op reranker: preserves retrieval order and score."""

    model_name = "none"

    async def rerank(
        self, query: str, candidates: list[EvidenceChunk]
    ) -> list[EvidenceChunk]:
        return [
            dataclasses.replace(c, rerank_score=c.retrieval_score) for c in candidates
        ]


@lru_cache
def get_reranker(model_name: str | None = None, enabled: bool | None = None) -> Reranker:
    """Application-wide reranker singleton.

    Falls back to the passthrough reranker when disabled or when the
    sentence-transformers stack isn't installed, so context fusion
    degrades instead of failing the request. Takes hashable primitives
    (not the Settings object) so the result is cacheable.
    """
    settings: Settings = get_settings()
    model_name = model_name or settings.reranker_model_name
    enabled = settings.reranker_enabled if enabled is None else enabled

    if not enabled or not cross_encoder_available():
        if enabled:
            logger.warning(
                "reranker_unavailable_using_passthrough",
                hint="install sentence-transformers to enable cross-encoder reranking",
            )
        return PassthroughReranker()
    return CrossEncoderReranker(model_name)
