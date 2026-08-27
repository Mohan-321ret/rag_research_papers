"""Schemas for cross-document knowledge conflicts (Phase 13)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeConflictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_a_chunk_id: uuid.UUID
    claim_a_document_id: uuid.UUID
    claim_a_content: str
    claim_b_chunk_id: uuid.UUID
    claim_b_document_id: uuid.UUID
    claim_b_content: str
    contradiction_score: float
    preferred_chunk_id: uuid.UUID | None
    resolved: bool
    resolution_reason: str
    created_at: datetime


class ConflictListResponse(BaseModel):
    items: list[KnowledgeConflictRead]
    total: int
    limit: int
    offset: int
