"""Knowledge browsing endpoints. All logic lives in KnowledgeService."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, KnowledgeServiceDep
from app.schemas.knowledge import (
    DriftListResponse,
    EntityListResponse,
    KnowledgeVersionListResponse,
    RelationshipListResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get(
    "/entities",
    response_model=EntityListResponse,
    summary="Entities extracted from the corpus",
)
async def list_entities(
    service: KnowledgeServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    entity_type: Annotated[str | None, Query(max_length=100)] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    document_id: uuid.UUID | None = None,
) -> EntityListResponse:
    return await service.entities(
        limit=limit,
        offset=offset,
        entity_type=entity_type,
        search=search,
        document_id=document_id,
    )


@router.get(
    "/relationships",
    response_model=RelationshipListResponse,
    summary="Relationships between extracted entities",
)
async def list_relationships(
    service: KnowledgeServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    relation_type: Annotated[str | None, Query(max_length=100)] = None,
) -> RelationshipListResponse:
    return await service.relationships(
        limit=limit, offset=offset, relation_type=relation_type
    )


@router.get(
    "/versions",
    response_model=KnowledgeVersionListResponse,
    summary="Corpus-wide version history (active + deprecated), newest first",
)
async def list_versions(
    service: KnowledgeServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KnowledgeVersionListResponse:
    return await service.versions(limit=limit, offset=offset)


@router.get(
    "/drift",
    response_model=DriftListResponse,
    summary="Corpus-wide knowledge drift feed across version transitions",
)
async def list_drift(
    service: KnowledgeServiceDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    min_drift: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
) -> DriftListResponse:
    return await service.drift(limit=limit, offset=offset, min_drift=min_drift)
