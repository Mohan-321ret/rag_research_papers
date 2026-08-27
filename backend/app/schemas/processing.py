"""Schemas for the processing pipeline endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    document_id: uuid.UUID | None
    version_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int | None
    page_number: int | None
    section: str | None
    embedding_ref: str | None
    # The ORM attribute is chunk_metadata ("metadata" is SQLAlchemy's registry).
    metadata: dict[str, Any] = Field(validation_alias="chunk_metadata")
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: list[ChunkRead]
    total: int
    limit: int
    offset: int
    version_id: uuid.UUID
    version_number: int


class ProcessingResult(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    status: str
    language: str
    language_confidence: float
    chunk_count: int
    # Embeddings actually computed this run — the expensive work. With
    # incremental re-indexing this is only the *changed* chunks, so
    # embedded_count + chunks_reused == chunk_count.
    embedded_count: int
    chunks_reused: int
    vectors_added: int
    vectors_removed: int
    incremental: bool
    noise_lines_removed: int
    embedding_model: str
    vector_backend: str
