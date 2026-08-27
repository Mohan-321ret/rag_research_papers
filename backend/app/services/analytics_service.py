"""Analytics service (Phase 15).

Aggregates what every earlier module already persisted — no new
bookkeeping, no separate metrics pipeline. The dashboard is a read over
documents/versions/chunks/entities (corpus), queries/answers/feedback
(usage), the verification fields Module 9 writes on each answer
(quality), and the Phase 11-13 evolution/conflict records (drift).
"""

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.evolution_repository import EvolutionRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.analytics import (
    CorpusStats,
    DashboardResponse,
    MetricsResponse,
    QualityStats,
    UsageStats,
)


class AnalyticsService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        knowledge_repository: KnowledgeRepository,
        interaction_repository: InteractionRepository,
        evolution_repository: EvolutionRepository,
        conflict_repository: ConflictRepository,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._knowledge = knowledge_repository
        self._interactions = interaction_repository
        self._evolution = evolution_repository
        self._conflicts = conflict_repository

    async def corpus_stats(self) -> CorpusStats:
        chunk_count, _ = await self._chunks.corpus_fingerprint()
        return CorpusStats(
            documents=await self._documents.count_documents(),
            versions=await self._documents.count_versions(),
            chunks=chunk_count,
            entities=await self._knowledge.count_entities(),
            documents_by_status=await self._documents.status_counts(),
        )

    async def dashboard(self) -> DashboardResponse:
        _, conflict_total = await self._conflicts.list_all(limit=1, offset=0)
        stats = await self._interactions.answer_stats()
        return DashboardResponse(
            corpus=await self.corpus_stats(),
            usage=UsageStats(
                queries=await self._interactions.count_queries(),
                answers=await self._interactions.count_answers(),
                feedback_by_rating=await self._interactions.feedback_counts(),
            ),
            quality=QualityStats(
                avg_latency_ms=stats["avg_latency_ms"],
                avg_confidence=stats["avg_confidence"],
                ungrounded_answers=stats["ungrounded_answers"],
            ),
            drift=await self._evolution.drift_summary(),
            conflicts=conflict_total,
        )

    async def metrics(self) -> MetricsResponse:
        return MetricsResponse(
            intents=await self._interactions.intent_counts(),
            retrievers=await self._interactions.retriever_counts(),
            entity_types=await self._knowledge.entity_type_counts(),
            drift_magnitudes=await self._evolution.drift_summary(),
            documents_by_status=await self._documents.status_counts(),
            feedback_by_rating=await self._interactions.feedback_counts(),
        )
