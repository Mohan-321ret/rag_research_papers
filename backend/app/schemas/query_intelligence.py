"""Schemas for query intelligence output."""

from pydantic import BaseModel

from app.modules.query_intelligence.analyzer import StructuredQuery
from app.modules.query_intelligence.interfaces import QueryIntent


class StructuredQueryRead(BaseModel):
    original_query: str
    normalized_query: str
    intent: QueryIntent
    entities: list[str]
    keywords: list[str]
    complexity: str
    complexity_score: int
    sub_queries: list[str]
    temporal: bool
    temporal_direction: str | None
    target_date: str | None
    expanded_query: list[str]

    @classmethod
    def from_structured(cls, structured: StructuredQuery) -> "StructuredQueryRead":
        return cls(
            original_query=structured.original_query,
            normalized_query=structured.normalized_query,
            intent=structured.intent,
            entities=structured.entities,
            keywords=structured.keywords,
            complexity=structured.complexity,
            complexity_score=structured.complexity_score,
            sub_queries=structured.sub_queries,
            temporal=structured.temporal,
            temporal_direction=structured.temporal_direction,
            target_date=structured.target_date,
            expanded_query=structured.expanded_query,
        )
