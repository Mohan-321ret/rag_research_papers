"""Schemas for the knowledge browsing endpoints (Phase 15)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    entity_type: str
    description: str | None
    document_id: uuid.UUID | None
    properties: dict[str, Any]
    created_at: datetime


class EntityListResponse(BaseModel):
    items: list[EntityRead]
    total: int
    limit: int
    offset: int


class RelationshipRead(BaseModel):
    id: uuid.UUID
    relation_type: str
    confidence: float | None
    properties: dict[str, Any]
    created_at: datetime
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    # Hydrated for display so a UI needn't make N follow-up calls.
    source_name: str | None
    target_name: str | None


class RelationshipListResponse(BaseModel):
    items: list[RelationshipRead]
    total: int
    limit: int
    offset: int


class KnowledgeVersionRead(BaseModel):
    """One version in the corpus-wide version feed."""

    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    version_number: int
    content_hash: str
    is_current: bool
    status: str  # "active" | "deprecated"
    created_at: datetime


class KnowledgeVersionListResponse(BaseModel):
    items: list[KnowledgeVersionRead]
    total: int
    limit: int
    offset: int


class DriftEntry(BaseModel):
    """One version transition in the corpus-wide drift feed."""

    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    from_version_number: int | None
    to_version_number: int
    change_type: str
    text_similarity: float
    drift_score: float
    drift_magnitude: str
    has_conflict: bool
    summary: str
    created_at: datetime


class DriftListResponse(BaseModel):
    items: list[DriftEntry]
    total: int
    limit: int
    offset: int
    summary: dict[str, int]  # counts by magnitude, plus with_conflict
