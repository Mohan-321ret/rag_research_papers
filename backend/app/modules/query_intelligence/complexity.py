"""Query complexity analysis and sub-query decomposition."""

import re
from dataclasses import dataclass, field

from app.modules.query_intelligence.interfaces import QueryIntent
from app.modules.query_intelligence.parser import ParsedQuery

_CLAUSE_SPLIT = re.compile(r"\s+and\s+|;\s*|\?\s+", re.IGNORECASE)
_CONJUNCTIONS = re.compile(r"\b(and|as well as|along with|also)\b")


@dataclass(frozen=True, slots=True)
class ComplexityResult:
    level: str  # "simple" | "moderate" | "complex"
    score: int
    sub_queries: list[str] = field(default_factory=list)


def analyze_complexity(
    parsed: ParsedQuery, intent: QueryIntent, entities: list[str]
) -> ComplexityResult:
    """Score structural complexity and split compound questions."""
    score = 0
    if len(parsed.tokens) > 15:
        score += 1
    if len(entities) >= 3:
        score += 1
    if _CONJUNCTIONS.search(parsed.normalized):
        score += 1
    if intent in (QueryIntent.COMPARATIVE, QueryIntent.ANALYTICAL):
        score += 1
    if parsed.original.count("?") > 1:
        score += 1

    level = "simple" if score <= 1 else ("moderate" if score == 2 else "complex")

    sub_queries: list[str] = []
    if level != "simple":
        parts = [
            part.strip(" ?.")
            for part in _CLAUSE_SPLIT.split(parsed.original)
            if len(part.strip().split()) >= 3
        ]
        if len(parts) > 1:
            sub_queries = parts

    return ComplexityResult(level=level, score=score, sub_queries=sub_queries)
