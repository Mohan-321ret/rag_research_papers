"""Admin service (Phase 15): operational visibility.

``/admin/system-status`` extends the public health check with what an
operator actually needs to know about *this* system: which optional ML
features are genuinely live right now (enabled in config **and** with
their dependency importable — the same two conditions the services
themselves check before using them), plus corpus size.
"""

import uuid

from app.core.config import Settings
from app.modules.context_fusion.reranker import cross_encoder_available
from app.modules.llm.providers import anthropic_available, ollama_configured
from app.modules.processing.embedding import embedding_stack_available
from app.modules.verification.nli_verifier import nli_available
from app.repositories.audit_repository import AuditRepository
from app.schemas.admin import (
    AuditLogListResponse,
    AuditLogRead,
    ModuleStatus,
    SystemStatusResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.health_service import HealthService


class AdminService:
    def __init__(
        self,
        settings: Settings,
        health_service: HealthService,
        analytics_service: AnalyticsService,
        audit_repository: AuditRepository,
    ) -> None:
        self._settings = settings
        self._health = health_service
        self._analytics = analytics_service
        self._audit = audit_repository

    async def system_status(self) -> SystemStatusResponse:
        health = await self._health.get_health()
        corpus = await self._analytics.corpus_stats()
        return SystemStatusResponse(
            status=health.status,
            app=health.app,
            version=health.version,
            environment=health.environment,
            timestamp=health.timestamp,
            components=health.components,
            modules=self._module_statuses(),
            corpus={
                "documents": corpus.documents,
                "versions": corpus.versions,
                "chunks": corpus.chunks,
                "entities": corpus.entities,
            },
        )

    def _module_statuses(self) -> list[ModuleStatus]:
        embeddings = embedding_stack_available()
        nli = nli_available()
        return [
            ModuleStatus(
                name="embeddings",
                enabled=embeddings,
                detail=self._settings.embedding_model_name if embeddings else
                "sentence-transformers not installed",
            ),
            ModuleStatus(
                name="reranker",
                enabled=self._settings.reranker_enabled and cross_encoder_available(),
                detail=self._settings.reranker_model_name,
            ),
            ModuleStatus(
                name="verification",
                enabled=self._settings.verification_enabled and nli,
                detail=self._settings.verification_model_name,
            ),
            ModuleStatus(
                name="knowledge_evolution",
                enabled=self._settings.evolution_enabled and nli,
                detail="drift + conflict detection across versions",
            ),
            ModuleStatus(
                name="conflict_detection",
                enabled=self._settings.conflict_detection_enabled and nli,
                detail="cross-document contradiction detection",
            ),
            ModuleStatus(
                name="incremental_reindex",
                enabled=self._settings.incremental_reindex_enabled,
                detail="embed only changed chunks",
            ),
            ModuleStatus(
                name="llm",
                enabled=True,
                detail=self._active_llm_detail(),
            ),
            ModuleStatus(
                name="graph_sync",
                enabled=self._settings.graph_auto_sync,
                detail="Neo4j projection on every processed version",
            ),
        ]

    def _active_llm_detail(self) -> str:
        """Which provider a request would actually use right now — mirrors
        build_answer_generator's selection rules."""
        provider = self._settings.llm_provider
        if provider == "extractive":
            return "extractive baseline (no LLM)"
        if provider == "anthropic":
            return f"anthropic:{self._settings.llm_model}"
        if provider == "ollama":
            return f"ollama:{self._settings.ollama_model}"
        if anthropic_available():
            return f"auto -> anthropic:{self._settings.llm_model}"
        if ollama_configured():
            return f"auto -> ollama:{self._settings.ollama_model}"
        return "auto -> extractive baseline"

    async def audit_logs(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None,
        user_id: uuid.UUID | None,
    ) -> AuditLogListResponse:
        items, total = await self._audit.list_logs(
            limit=limit, offset=offset, action=action, user_id=user_id
        )
        return AuditLogListResponse(
            items=[AuditLogRead.model_validate(entry) for entry in items],
            total=total,
            limit=limit,
            offset=offset,
        )
