"""Contracts for understanding and preparing user queries."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class QueryIntent(StrEnum):
    FACTUAL_LOOKUP = "factual_lookup"
    ANALYTICAL = "analytical"
    COMPARATIVE = "comparative"
    PROCEDURAL = "procedural"
    SUMMARIZATION = "summarization"


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """The analyzed form of a user query used to drive retrieval."""

    original_query: str
    normalized_query: str
    intent: QueryIntent
    sub_queries: Sequence[str]


class QueryAnalyzer(ABC):
    """Classifies intent and decomposes/rewrites queries."""

    @abstractmethod
    async def analyze(self, query: str) -> QueryPlan: ...
