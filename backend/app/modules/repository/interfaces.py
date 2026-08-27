"""Contracts for the knowledge stores backing retrieval.

FAISS will implement ``VectorIndex``; Neo4j will implement
``KnowledgeGraphStore``.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    chunk_id: str
    score: float


class VectorIndex(ABC):
    """Dense vector index over chunk embeddings."""

    @abstractmethod
    async def add(self, chunk_ids: Sequence[str], vectors: Sequence[Sequence[float]]) -> None: ...

    @abstractmethod
    async def search(self, vector: Sequence[float], k: int) -> Sequence[VectorSearchHit]: ...

    @abstractmethod
    async def remove(self, chunk_ids: Sequence[str]) -> None: ...


class KnowledgeGraphStore(ABC):
    """Entity/relation store capturing structure across documents."""

    @abstractmethod
    async def upsert_entity(self, entity_id: str, labels: Sequence[str], properties: Mapping[str, object]) -> None: ...

    @abstractmethod
    async def relate(self, source_id: str, relation: str, target_id: str, properties: Mapping[str, object] | None = None) -> None: ...

    @abstractmethod
    async def neighbors(self, entity_id: str, depth: int = 1) -> Sequence[str]: ...
