"""Contracts for retrieving evidence for a query plan."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.processing.interfaces import Chunk
from app.modules.query_intelligence.interfaces import QueryPlan


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk with its retrieval provenance and drift context."""

    chunk: Chunk
    score: float
    retriever: str
    drift_penalty: float = 0.0


class Retriever(ABC):
    """Retrieves candidate chunks for an analyzed query.

    Implementations may combine vector, graph and keyword retrieval and
    must account for drift signals when ranking (the "drift-aware" part).
    """

    @abstractmethod
    async def retrieve(self, plan: QueryPlan, k: int = 10) -> Sequence[RetrievedChunk]: ...
