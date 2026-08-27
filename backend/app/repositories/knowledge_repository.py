"""Data access for extracted knowledge entities (PostgreSQL side)."""

import uuid

from sqlalchemy import delete, func, select

from app.models.knowledge import KnowledgeEntity, KnowledgeRelationship
from app.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository):
    async def replace_document_entities(
        self, document_id: uuid.UUID, entities: list[tuple[str, str]]
    ) -> list[KnowledgeEntity]:
        """Replace the entity set extracted from a document.

        ``entities`` is a list of (name, entity_type) pairs, already
        deduplicated by the caller.
        """
        await self._session.execute(
            delete(KnowledgeEntity).where(KnowledgeEntity.document_id == document_id)
        )
        rows = [
            KnowledgeEntity(name=name, entity_type=entity_type, document_id=document_id)
            for name, entity_type in entities
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def list_entity_names(self, *, limit: int = 500) -> list[str]:
        """Distinct entity names across the corpus (for query NER matching)."""
        result = await self._session.execute(
            select(KnowledgeEntity.name).distinct().limit(limit)
        )
        return [name for (name,) in result.all()]

    async def list_for_document(self, document_id: uuid.UUID) -> list[KnowledgeEntity]:
        result = await self._session.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.document_id == document_id)
        )
        return list(result.scalars().all())

    async def list_entities(
        self,
        *,
        limit: int,
        offset: int,
        entity_type: str | None = None,
        search: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> tuple[list[KnowledgeEntity], int]:
        query = select(KnowledgeEntity)
        if entity_type:
            query = query.where(KnowledgeEntity.entity_type == entity_type)
        if search:
            query = query.where(KnowledgeEntity.name.ilike(f"%{search}%"))
        if document_id:
            query = query.where(KnowledgeEntity.document_id == document_id)

        total = await self._session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        result = await self._session.execute(
            query.order_by(KnowledgeEntity.name).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def list_relationships(
        self, *, limit: int, offset: int, relation_type: str | None = None
    ) -> tuple[list[KnowledgeRelationship], int]:
        query = select(KnowledgeRelationship)
        if relation_type:
            query = query.where(KnowledgeRelationship.relation_type == relation_type)

        total = await self._session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        result = await self._session.execute(
            query.order_by(KnowledgeRelationship.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def entities_by_id(
        self, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, KnowledgeEntity]:
        """Hydrate relationship endpoints into readable names."""
        if not entity_ids:
            return {}
        result = await self._session.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.id.in_(entity_ids))
        )
        return {entity.id: entity for entity in result.scalars().all()}

    async def count_entities(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(KnowledgeEntity)) or 0)

    async def entity_type_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            select(KnowledgeEntity.entity_type, func.count())
            .group_by(KnowledgeEntity.entity_type)
            .order_by(func.count().desc())
        )
        return {entity_type: int(count) for entity_type, count in result.all()}
