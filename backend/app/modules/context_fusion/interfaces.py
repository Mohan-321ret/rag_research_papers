"""Contracts for fusing retrieved evidence into an LLM-ready context."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.retrieval.interfaces import RetrievedChunk


@dataclass(frozen=True, slots=True)
class FusedContext:
    """Deduplicated, ordered evidence within a token budget."""

    text: str
    source_chunk_ids: Sequence[str]
    token_estimate: int


class ContextFuser(ABC):
    """Merges retrieved chunks, resolving conflicts between versions."""

    @abstractmethod
    async def fuse(self, query: str, chunks: Sequence[RetrievedChunk], *, max_tokens: int) -> FusedContext: ...
