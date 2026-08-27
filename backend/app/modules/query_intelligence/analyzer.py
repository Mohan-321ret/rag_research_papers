"""The query intelligence pipeline: raw query -> structured query.

Composes: parser -> intent detection -> NER -> complexity analysis ->
temporal detection -> context expansion.
"""

from dataclasses import dataclass, field

from app.modules.query_intelligence.complexity import analyze_complexity
from app.modules.query_intelligence.expansion import expand_entities
from app.modules.query_intelligence.intent import detect_intent
from app.modules.query_intelligence.interfaces import QueryIntent
from app.modules.query_intelligence.ner import extract_query_entities
from app.modules.query_intelligence.parser import parse_query
from app.modules.query_intelligence.temporal import detect_temporal


@dataclass(frozen=True, slots=True)
class StructuredQuery:
    """The analyzed form of a user query, driving retrieval decisions."""

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
    expanded_query: list[str] = field(default_factory=list)


def analyze_query(query: str, known_entities: list[str]) -> StructuredQuery:
    """Run the full pipeline over one query."""
    parsed = parse_query(query)
    intent = detect_intent(parsed)
    entities = extract_query_entities(parsed, known_entities)
    complexity = analyze_complexity(parsed, intent, entities)
    temporal = detect_temporal(parsed.normalized)
    expanded = expand_entities(entities)

    return StructuredQuery(
        original_query=parsed.original,
        normalized_query=parsed.normalized,
        intent=intent,
        entities=entities,
        keywords=parsed.keywords,
        complexity=complexity.level,
        complexity_score=complexity.score,
        sub_queries=complexity.sub_queries,
        temporal=temporal.is_temporal,
        temporal_direction=temporal.direction,
        target_date=temporal.target_date,
        expanded_query=expanded,
    )
