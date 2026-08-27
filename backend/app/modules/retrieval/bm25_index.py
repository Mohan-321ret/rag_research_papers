"""BM25 sparse retrieval over current-version chunks.

The index is built in memory with rank-bm25 and cached; a cheap corpus
fingerprint (chunk count + newest chunk id) detects staleness after
uploads/reprocessing and triggers a rebuild. Suitable for research-scale
corpora; swap for an inverted-index service at production scale.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-']*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True, slots=True)
class Bm25Hit:
    chunk_id: uuid.UUID
    score: float


class Bm25Index:
    """Cached BM25 index over (chunk_id, content) pairs."""

    def __init__(self) -> None:
        self._fingerprint: tuple[int, str] | None = None
        self._chunk_ids: list[uuid.UUID] = []
        self._bm25 = None
        self._lock = asyncio.Lock()

    async def ensure_built(
        self,
        fingerprint: tuple[int, str],
        corpus_loader,
    ) -> None:
        """(Re)build the index when the corpus fingerprint changed.

        ``corpus_loader`` is an async callable returning
        ``list[tuple[uuid.UUID, str]]``.
        """
        async with self._lock:
            if self._fingerprint == fingerprint and self._bm25 is not None:
                return
            corpus = await corpus_loader()
            from rank_bm25 import BM25Okapi

            self._chunk_ids = [chunk_id for chunk_id, _ in corpus]
            tokenized = [_tokenize(content) for _, content in corpus]
            self._bm25 = BM25Okapi(tokenized) if tokenized else None
            self._fingerprint = fingerprint
            logger.info("bm25_index_built", chunks=len(corpus))

    async def search(self, query: str, k: int) -> list[Bm25Hit]:
        async with self._lock:
            if self._bm25 is None or not self._chunk_ids:
                return []
            tokens = _tokenize(query)
            if not tokens:
                return []
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(
                zip(self._chunk_ids, scores), key=lambda pair: pair[1], reverse=True
            )
            return [
                Bm25Hit(chunk_id=chunk_id, score=float(score))
                for chunk_id, score in ranked[:k]
                if score > 0.0
            ]


_index_instance: Bm25Index | None = None


def get_bm25_index() -> Bm25Index:
    global _index_instance
    if _index_instance is None:
        _index_instance = Bm25Index()
    return _index_instance


def reset_bm25_index() -> None:
    """Testing hook."""
    global _index_instance
    _index_instance = None
