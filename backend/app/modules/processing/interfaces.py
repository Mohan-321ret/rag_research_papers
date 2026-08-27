"""Contracts for turning raw documents into embeddable chunks."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable unit of text derived from a document."""

    document_id: str
    text: str
    position: int
    metadata: Mapping[str, str] = field(default_factory=dict)


class Chunker(ABC):
    """Splits document text into chunks (LangChain splitters later)."""

    @abstractmethod
    def split(self, document_id: str, text: str) -> Sequence[Chunk]: ...


class EmbeddingModel(ABC):
    """Encodes text into dense vectors (Sentence Transformers later)."""

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...
