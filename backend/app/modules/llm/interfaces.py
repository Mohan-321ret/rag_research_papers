"""Contracts for answer generation (LangChain-backed later)."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.modules.context_fusion.interfaces import FusedContext


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """A generated answer with usage accounting."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class AnswerGenerator(ABC):
    """Generates grounded answers from a query and fused context."""

    @abstractmethod
    async def generate(self, query: str, context: FusedContext) -> GenerationResult: ...

    @abstractmethod
    def stream(self, query: str, context: FusedContext) -> AsyncIterator[str]: ...
