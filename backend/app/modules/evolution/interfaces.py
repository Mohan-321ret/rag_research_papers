"""Contracts for detecting and reacting to knowledge drift.

Drift-awareness is the core research contribution of DAA-RAG: the system
must notice when stored knowledge diverges from newly ingested content
(semantic drift) or when the embedding space itself shifts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DriftKind(StrEnum):
    CONTENT = "content"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"


@dataclass(frozen=True, slots=True)
class DriftSignal:
    """A detected divergence between knowledge versions."""

    document_id: str
    kind: DriftKind
    score: float
    detected_at: datetime
    description: str


class DriftDetector(ABC):
    """Compares knowledge versions and emits drift signals."""

    @abstractmethod
    async def detect(self, document_id: str) -> list[DriftSignal]: ...


class KnowledgeVersioner(ABC):
    """Tracks document versions so drift can be measured over time."""

    @abstractmethod
    async def register_version(self, document_id: str, content_hash: str) -> int:
        """Record a new version and return its version number."""
