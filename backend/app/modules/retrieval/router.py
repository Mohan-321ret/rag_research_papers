"""Deterministic retrieval routing.

Maps the structured query (from query intelligence) to a retrieval
strategy:

    exact term / ID / clause      -> BM25 (sparse keyword match)
    relationship / multi-hop      -> GRAPH (Neo4j)
    complex question              -> HYBRID (all retrievers + fusion)
    conceptual question (default) -> VECTOR (FAISS)

Deliberately simple rules; a learned router can replace this later
without touching the retrievers.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.query_intelligence.analyzer import StructuredQuery


class RetrievalRoute(StrEnum):
    BM25 = "bm25"
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


# Identifiers and codes: POL-123, ISO27001, GDPR-7, ticket/document numbers.
_ID_PATTERN = re.compile(r"\b[A-Za-z]{2,}-\d+\b|\b[A-Z]{2,}\d{2,}\b")
# Clause references: "section 4.2", "clause 7", "article 12", "policy 3.1".
_CLAUSE_PATTERN = re.compile(
    r"\b(section|clause|article|paragraph|appendix|chapter)\s+\d+(\.\d+)*\b",
    re.IGNORECASE,
)
_QUOTED_PHRASE = re.compile(r"\"[^\"]+\"|'[^']{4,}'")

# Relationship / multi-hop phrasing.
_RELATIONSHIP_PATTERN = re.compile(
    r"\b(related to|relationship|relate|connected (to|with)|connection|"
    r"link(ed|s)? (to|between)|between .+ and .+|who (wrote|authored|created)|"
    r"which (documents?|files?|policies) (mention|reference|contain|cover)|"
    r"associated with|depends? on|refers? to)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    route: RetrievalRoute
    reasons: list[str] = field(default_factory=list)


def decide_route(structured: StructuredQuery) -> RoutingDecision:
    """Pick a retrieval strategy for the analyzed query."""
    text = structured.original_query
    reasons: list[str] = []

    if _ID_PATTERN.search(text):
        reasons.append("contains identifier/code")
    if _CLAUSE_PATTERN.search(text):
        reasons.append("references a clause/section number")
    if _QUOTED_PHRASE.search(text):
        reasons.append("contains quoted exact phrase")
    if structured.keywords and len(structured.keywords) <= 3 and not text.endswith("?"):
        reasons.append("short keyword-style query")
    if reasons:
        return RoutingDecision(route=RetrievalRoute.BM25, reasons=reasons)

    if _RELATIONSHIP_PATTERN.search(text):
        return RoutingDecision(
            route=RetrievalRoute.GRAPH,
            reasons=["relationship/multi-hop phrasing"],
        )

    if structured.complexity == "complex":
        return RoutingDecision(
            route=RetrievalRoute.HYBRID,
            reasons=[f"complex query (score {structured.complexity_score})"],
        )

    return RoutingDecision(route=RetrievalRoute.VECTOR, reasons=["conceptual question"])
