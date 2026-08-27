"""Query intelligence service: analysis backed by corpus knowledge."""

from app.core.logging import get_logger
from app.modules.query_intelligence.analyzer import StructuredQuery, analyze_query
from app.repositories.knowledge_repository import KnowledgeRepository

logger = get_logger(__name__)


class QueryIntelligenceService:
    def __init__(self, knowledge_repository: KnowledgeRepository) -> None:
        self._knowledge = knowledge_repository

    async def analyze(self, query: str) -> StructuredQuery:
        """Analyze a query, matching entities against the knowledge base."""
        known_entities = await self._knowledge.list_entity_names()
        structured = analyze_query(query, known_entities)
        logger.info(
            "query_analyzed",
            intent=structured.intent.value,
            complexity=structured.complexity,
            temporal=structured.temporal,
            entities=len(structured.entities),
            expansions=len(structured.expanded_query),
        )
        return structured
