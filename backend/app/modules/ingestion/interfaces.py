"""Contracts for acquiring documents from enterprise knowledge sources."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RawDocument:
    """A document as delivered by a source, before any processing."""

    source_uri: str
    content: bytes
    media_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)


class DocumentSource(ABC):
    """A connector to an external knowledge source (filesystem, wiki, ...)."""

    @abstractmethod
    async def fetch(self, source_uri: str) -> RawDocument:
        """Fetch a single document by its source URI."""


class IngestionPipeline(ABC):
    """Coordinates fetching, deduplication and registration of documents."""

    @abstractmethod
    async def ingest(self, source_uri: str) -> str:
        """Ingest one document and return its internal document id."""
