"""Knowledge browsing service (Phase 15).

Read-only views over what the pipeline has already extracted and
recorded: entities and relationships (Modules 2/4), the corpus-wide
version history (Module 3 / Phase 11), and the drift feed (Phases 11-12).
"""

import uuid

from app.repositories.document_repository import DocumentRepository
from app.repositories.evolution_repository import EvolutionRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    DriftEntry,
    DriftListResponse,
    EntityListResponse,
    EntityRead,
    KnowledgeVersionListResponse,
    KnowledgeVersionRead,
    RelationshipListResponse,
    RelationshipRead,
)


class KnowledgeService:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        document_repository: DocumentRepository,
        evolution_repository: EvolutionRepository,
    ) -> None:
        self._knowledge = knowledge_repository
        self._documents = document_repository
        self._evolution = evolution_repository

    async def entities(
        self,
        *,
        limit: int,
        offset: int,
        entity_type: str | None,
        search: str | None,
        document_id: uuid.UUID | None,
    ) -> EntityListResponse:
        items, total = await self._knowledge.list_entities(
            limit=limit,
            offset=offset,
            entity_type=entity_type,
            search=search,
            document_id=document_id,
        )
        return EntityListResponse(
            items=[EntityRead.model_validate(e) for e in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def relationships(
        self, *, limit: int, offset: int, relation_type: str | None
    ) -> RelationshipListResponse:
        items, total = await self._knowledge.list_relationships(
            limit=limit, offset=offset, relation_type=relation_type
        )
        # Hydrate both endpoints in one lookup so the caller gets readable
        # names instead of having to resolve every id itself.
        referenced = {r.source_entity_id for r in items} | {r.target_entity_id for r in items}
        by_id = await self._knowledge.entities_by_id(list(referenced))
        return RelationshipListResponse(
            items=[
                RelationshipRead(
                    id=r.id,
                    relation_type=r.relation_type,
                    confidence=r.confidence,
                    properties=r.properties,
                    created_at=r.created_at,
                    source_entity_id=r.source_entity_id,
                    target_entity_id=r.target_entity_id,
                    source_name=(e.name if (e := by_id.get(r.source_entity_id)) else None),
                    target_name=(e.name if (e := by_id.get(r.target_entity_id)) else None),
                )
                for r in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def versions(self, *, limit: int, offset: int) -> KnowledgeVersionListResponse:
        rows, total = await self._documents.list_recent_versions(limit=limit, offset=offset)
        return KnowledgeVersionListResponse(
            items=[
                KnowledgeVersionRead(
                    id=version.id,
                    document_id=version.document_id,
                    document_title=title,
                    version_number=version.version_number,
                    content_hash=version.content_hash,
                    is_current=version.is_current,
                    status="active" if version.is_current else "deprecated",
                    created_at=version.created_at,
                )
                for version, title in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def drift(
        self, *, limit: int, offset: int, min_drift: float | None
    ) -> DriftListResponse:
        rows, total = await self._evolution.list_recent_drift(
            limit=limit, offset=offset, min_drift=min_drift
        )
        return DriftListResponse(
            items=[
                DriftEntry(
                    id=row.id,
                    document_id=row.document_id,
                    document_title=title,
                    from_version_number=row.from_version_number,
                    to_version_number=row.to_version_number,
                    change_type=row.change_type,
                    text_similarity=row.text_similarity,
                    drift_score=row.drift_score,
                    drift_magnitude=row.drift_magnitude,
                    has_conflict=row.has_conflict,
                    summary=row.summary,
                    created_at=row.created_at,
                )
                for row, title in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
            summary=await self._evolution.drift_summary(),
        )
