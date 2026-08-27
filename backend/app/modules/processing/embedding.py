"""Embedding generation backed by Sentence Transformers.

The model is loaded lazily (first use) and encoding runs in a worker
thread so the event loop is never blocked. When the sentence-transformers
stack is not installed (e.g. an interpreter without torch wheels), the
processing pipeline reports itself unavailable instead of crashing.
"""

import asyncio
import importlib.util
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger
from app.modules.processing.interfaces import EmbeddingModel

logger = get_logger(__name__)


def embedding_stack_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class SentenceTransformerEmbedder(EmbeddingModel):
    """all-MiniLM-L6-v2 (or configured model), normalized embeddings."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None
        self._dimension: int | None = None
        self._lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise RuntimeError("Embedding model not loaded yet; call embed_texts first")
        return self._dimension

    async def load(self) -> None:
        """Load the model (downloads it on first ever use)."""
        async with self._lock:
            if self._model is not None:
                return
            if not embedding_stack_available():
                raise ServiceUnavailableError(
                    "Embedding model unavailable: sentence-transformers is not "
                    "installed in this environment"
                )
            logger.info("embedding_model_loading", model=self._model_name)
            self._model = await asyncio.to_thread(self._load_sync)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
            logger.info(
                "embedding_model_loaded", model=self._model_name, dimension=self._dimension
            )

    def _load_sync(self) -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self._model_name, device="cpu")

    async def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []
        await self.load()
        vectors = await asyncio.to_thread(
            self._model.encode,
            list(texts),
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in vector] for vector in vectors]


@lru_cache
def get_embedder(model_name: str | None = None) -> SentenceTransformerEmbedder:
    """Application-wide embedder singleton."""
    settings: Settings = get_settings()
    return SentenceTransformerEmbedder(model_name or settings.embedding_model_name)
