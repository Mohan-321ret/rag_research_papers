"""Schemas for document ingestion endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.document import DocumentStatus


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    content_hash: str
    is_current: bool
    created_at: datetime

    @computed_field
    @property
    def status(self) -> str:
        """"active" (the current version) or "deprecated" (superseded,
        but never deleted — still queryable for historical answers)."""
        return "active" if self.is_current else "deprecated"


class DocumentRead(BaseModel):
    id: uuid.UUID
    title: str
    source_uri: str | None
    source_type: str
    status: DocumentStatus
    metadata: dict[str, Any]
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    current_version: int | None
    version_count: int


class UploadResponse(DocumentRead):
    """Upload outcome: whether a new version was created or content matched."""

    new_version_created: bool
    deduplicated: bool


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    limit: int
    offset: int
