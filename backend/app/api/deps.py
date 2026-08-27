"""Shared FastAPI dependency providers wiring the layers together."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.neo4j import Neo4jClient, get_neo4j_client
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.modules.context_fusion.reranker import get_reranker
from app.modules.processing.embedding import get_embedder
from app.modules.repository.graph_store import GraphStore
from app.modules.verification.nli_verifier import get_nli_verifier
from app.repositories.audit_repository import AuditRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conflict_repository import ConflictRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.evolution_repository import EvolutionRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.system_repository import SystemRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.conflict_service import ConflictService
from app.services.context_fusion_service import ContextFusionService
from app.services.document_service import DocumentService
from app.services.evolution_service import EvolutionService
from app.services.feedback_service import FeedbackService
from app.services.graph_service import GraphService
from app.services.health_service import HealthService
from app.services.knowledge_service import KnowledgeService
from app.services.processing_service import ProcessingService
from app.services.query_intelligence_service import QueryIntelligenceService
from app.services.retrieval_service import RetrievalService
from app.services.search_service import SearchService
from app.services.verification_service import VerificationService

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
Neo4jClientDep = Annotated[Neo4jClient, Depends(get_neo4j_client)]


def get_system_repository(session: DbSessionDep) -> SystemRepository:
    return SystemRepository(session)


SystemRepositoryDep = Annotated[SystemRepository, Depends(get_system_repository)]


def get_health_service(
    settings: SettingsDep,
    system_repository: SystemRepositoryDep,
    neo4j_client: Neo4jClientDep,
) -> HealthService:
    return HealthService(settings, system_repository, neo4j_client)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


def get_user_repository(session: DbSessionDep) -> UserRepository:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_auth_service(settings: SettingsDep, session: DbSessionDep) -> AuthService:
    return AuthService(settings, session, UserRepository(session), AuditRepository(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_graph_service(session: DbSessionDep, neo4j_client: Neo4jClientDep) -> GraphService:
    return GraphService(
        DocumentRepository(session), ChunkRepository(session), GraphStore(neo4j_client)
    )


GraphServiceDep = Annotated[GraphService, Depends(get_graph_service)]


def get_evolution_service(settings: SettingsDep, session: DbSessionDep) -> EvolutionService:
    return EvolutionService(
        settings,
        EvolutionRepository(session),
        ChunkRepository(session),
        get_embedder(),
        # Its own enabled flag (not Module 9's) — the two features can be
        # toggled independently while still sharing the cached model when
        # both are on.
        get_nli_verifier(settings.verification_model_name, settings.evolution_enabled),
    )


EvolutionServiceDep = Annotated[EvolutionService, Depends(get_evolution_service)]


def get_conflict_service(settings: SettingsDep, session: DbSessionDep) -> ConflictService:
    return ConflictService(
        settings,
        ConflictRepository(session),
        DocumentRepository(session),
        ChunkRepository(session),
        get_embedder(),
        # Its own enabled flag, same reasoning as get_evolution_service.
        get_nli_verifier(settings.verification_model_name, settings.conflict_detection_enabled),
    )


ConflictServiceDep = Annotated[ConflictService, Depends(get_conflict_service)]


def get_processing_service(
    settings: SettingsDep,
    session: DbSessionDep,
    graph_service: GraphServiceDep,
    evolution_service: EvolutionServiceDep,
    conflict_service: ConflictServiceDep,
) -> ProcessingService:
    return ProcessingService(
        settings,
        session,
        DocumentRepository(session),
        ChunkRepository(session),
        get_embedder(),
        knowledge_repository=KnowledgeRepository(session),
        graph_service=graph_service,
        evolution_service=evolution_service,
        conflict_service=conflict_service,
    )


ProcessingServiceDep = Annotated[ProcessingService, Depends(get_processing_service)]


def get_document_service(
    settings: SettingsDep,
    session: DbSessionDep,
    processing_service: ProcessingServiceDep,
) -> DocumentService:
    return DocumentService(
        settings,
        session,
        DocumentRepository(session),
        AuditRepository(session),
        processing_service,
    )


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def get_query_intelligence_service(session: DbSessionDep) -> QueryIntelligenceService:
    return QueryIntelligenceService(KnowledgeRepository(session))


QueryIntelligenceServiceDep = Annotated[
    QueryIntelligenceService, Depends(get_query_intelligence_service)
]


def get_retrieval_service(
    settings: SettingsDep, session: DbSessionDep, neo4j_client: Neo4jClientDep
) -> RetrievalService:
    return RetrievalService(
        settings, ChunkRepository(session), get_embedder(), GraphStore(neo4j_client)
    )


RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


def get_context_fusion_service(
    settings: SettingsDep, session: DbSessionDep
) -> ContextFusionService:
    return ContextFusionService(settings, get_reranker(), ConflictRepository(session))


ContextFusionServiceDep = Annotated[
    ContextFusionService, Depends(get_context_fusion_service)
]


def get_verification_service(
    settings: SettingsDep, session: DbSessionDep
) -> VerificationService:
    return VerificationService(
        settings, ChunkRepository(session), get_embedder(), get_nli_verifier()
    )


VerificationServiceDep = Annotated[VerificationService, Depends(get_verification_service)]


def get_chat_service(
    settings: SettingsDep,
    session: DbSessionDep,
    query_intelligence: QueryIntelligenceServiceDep,
    retrieval: RetrievalServiceDep,
    context_fusion: ContextFusionServiceDep,
    verification: VerificationServiceDep,
) -> ChatService:
    return ChatService(
        settings,
        session,
        InteractionRepository(session),
        query_intelligence,
        retrieval,
        context_fusion,
        verification,
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_search_service(
    settings: SettingsDep,
    query_intelligence: QueryIntelligenceServiceDep,
    retrieval: RetrievalServiceDep,
    context_fusion: ContextFusionServiceDep,
) -> SearchService:
    return SearchService(settings, query_intelligence, retrieval, context_fusion)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_knowledge_service(session: DbSessionDep) -> KnowledgeService:
    return KnowledgeService(
        KnowledgeRepository(session),
        DocumentRepository(session),
        EvolutionRepository(session),
    )


KnowledgeServiceDep = Annotated[KnowledgeService, Depends(get_knowledge_service)]


def get_feedback_service(session: DbSessionDep) -> FeedbackService:
    return FeedbackService(
        session, InteractionRepository(session), AuditRepository(session)
    )


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


def get_analytics_service(session: DbSessionDep) -> AnalyticsService:
    return AnalyticsService(
        DocumentRepository(session),
        ChunkRepository(session),
        KnowledgeRepository(session),
        InteractionRepository(session),
        EvolutionRepository(session),
        ConflictRepository(session),
    )


AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


def get_admin_service(
    settings: SettingsDep,
    session: DbSessionDep,
    health_service: HealthServiceDep,
    analytics_service: AnalyticsServiceDep,
) -> AdminService:
    return AdminService(
        settings, health_service, analytics_service, AuditRepository(session)
    )


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    user_repository: UserRepositoryDep,
) -> User:
    """Resolve the authenticated user from the Authorization header."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated")

    payload = decode_token(credentials.credentials)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    user = await user_repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or deactivated")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):  # noqa: ANN201 - FastAPI dependency factory
    """Dependency guard restricting an endpoint to the given roles."""

    async def _check(user: CurrentUserDep) -> User:
        if user.role not in roles:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return Depends(_check)
