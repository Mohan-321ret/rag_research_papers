"""Knowledge graph entities and relationships (mirrored into Neo4j later)."""

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_entities"

    name: Mapped[str] = mapped_column(String(300), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Provenance: the document this entity was extracted from (if any).
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )


class KnowledgeRelationship(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_relationships"

    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"), index=True
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(100), index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None]

    source_entity: Mapped[KnowledgeEntity] = relationship(foreign_keys=[source_entity_id])
    target_entity: Mapped[KnowledgeEntity] = relationship(foreign_keys=[target_entity_id])
